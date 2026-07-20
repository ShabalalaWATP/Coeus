from coeus.application.ports.admission import ProviderAdmission
from coeus.application.ports.workflow_transaction import WorkflowTransactionPort
from coeus.core.config import Settings
from coeus.core.deployment import HOSTED_ENVIRONMENTS
from coeus.persistence.state_store import StateStore
from coeus.repositories.tickets import InMemoryTicketRepository
from coeus.services.admission_metrics import AdmissionMetrics
from coeus.services.ai_models import AiModelService
from coeus.services.audit import AuditLog
from coeus.services.configurable_intake_provider import ConfigurableIntakeProvider
from coeus.services.intake import IntakeExtractionService, RequirementCompletenessService
from coeus.services.postgres_provider_admission import PostgresProviderAdmissionController
from coeus.services.postgres_ticket_admission import PostgresTicketAdmissionController
from coeus.services.provider_admission import ProviderAdmissionController
from coeus.services.ticket_admission import TicketAdmissionController
from coeus.services.ticket_conversations import ConversationService
from coeus.services.tickets import TicketService, TicketServices


def build_ticket_services(
    settings: Settings,
    audit_log: AuditLog,
    state_store: StateStore | None = None,
    ai_models: AiModelService | None = None,
    transaction: WorkflowTransactionPort | None = None,
    admission_metrics: AdmissionMetrics | None = None,
    provider_admission: ProviderAdmission | None = None,
) -> TicketServices:
    metrics = admission_metrics or AdmissionMetrics()
    repository = InMemoryTicketRepository(state_store)
    completeness = RequirementCompletenessService()
    tickets = TicketService(repository, completeness, audit_log, transaction)
    conversations = ConversationService(
        repository,
        tickets,
        tickets.mutations,
        IntakeExtractionService(),
        ConfigurableIntakeProvider(settings, ai_models),
        audit_log,
        provider_admission or build_provider_admission(settings, metrics),
        _ticket_admission(settings, repository, metrics),
    )
    return TicketServices(
        tickets=tickets,
        conversations=conversations,
        mutations=tickets.mutations,
    )


def build_provider_admission(
    settings: Settings,
    metrics: AdmissionMetrics,
) -> ProviderAdmissionController | PostgresProviderAdmissionController:
    if settings.environment in HOSTED_ENVIRONMENTS:
        return PostgresProviderAdmissionController(
            settings.database_url,
            max_concurrent=settings.provider_max_concurrent,
            max_calls_per_window=settings.provider_max_calls_per_window,
            max_calls_per_principal=settings.provider_max_calls_per_principal,
            window_seconds=settings.provider_window_seconds,
            mode=settings.provider_admission_mode,
            metrics=metrics,
        )
    return ProviderAdmissionController(
        max_concurrent=settings.provider_max_concurrent,
        max_calls_per_window=settings.provider_max_calls_per_window,
        max_calls_per_principal=settings.provider_max_calls_per_principal,
        window_seconds=settings.provider_window_seconds,
        mode=settings.provider_admission_mode,
        metrics=metrics,
    )


def _ticket_admission(
    settings: Settings, repository: InMemoryTicketRepository, metrics: AdmissionMetrics
) -> TicketAdmissionController | PostgresTicketAdmissionController:
    if settings.environment in HOSTED_ENVIRONMENTS:
        return PostgresTicketAdmissionController(
            settings.database_url,
            max_retained=settings.ticket_max_retained,
            max_retained_per_principal=settings.ticket_max_retained_per_principal,
            mode=settings.ticket_admission_mode,
            metrics=metrics,
        )
    return TicketAdmissionController(
        repository,
        max_retained=settings.ticket_max_retained,
        max_retained_per_principal=settings.ticket_max_retained_per_principal,
        mode=settings.ticket_admission_mode,
        metrics=metrics,
    )
