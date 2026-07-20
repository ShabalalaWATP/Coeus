from fastapi import FastAPI

from coeus.api.identity_composition import IdentityComponents, configure_identity
from coeus.api.product_workflow_composition import configure_product_workflow
from coeus.api.search_composition import configure_search_services
from coeus.api.ticket_discovery_composition import build_ticket_discovery_handler
from coeus.application.ports.admission import ResourceAdmission
from coeus.core.config import HOSTED_ENVIRONMENTS, Settings
from coeus.persistence.factory import build_state_store
from coeus.persistence.outbox import PostgresOutboxStore
from coeus.persistence.state_store import PostgresStateStore
from coeus.persistence.workflow_transaction import PostgresWorkflowTransaction
from coeus.repositories.teams import TeamRepository
from coeus.repositories.teams_seed import seed_teams
from coeus.services.admin_analytics import AdminAnalyticsService
from coeus.services.admission_metrics import AdmissionMetrics
from coeus.services.ai_models import AiModelService
from coeus.services.analyst_assignment_service import AnalystAssignmentService
from coeus.services.analyst_workflow import AnalystWorkflowService
from coeus.services.asset_tokens import AssetTokenService
from coeus.services.demo_seed import seed_demo_dataset
from coeus.services.email_delivery import build_email_provider
from coeus.services.embeddings import build_embedding_service
from coeus.services.feedback_analytics import build_feedback_analytics_service
from coeus.services.integration_secrets import EncryptedIntegrationSecretStore
from coeus.services.jioc_routing_agent import JiocRoutingAgentService
from coeus.services.manager_approval import ManagerApprovalService
from coeus.services.manager_queue import ManagerQueueService
from coeus.services.notifications import NotificationService
from coeus.services.object_storage import build_object_storage
from coeus.services.outbox_dispatcher import OutboxDispatcher
from coeus.services.postgres_resource_admission import PostgresResourceAdmissionController
from coeus.services.quality_control import build_quality_control_service
from coeus.services.release_notification_handler import ProductReleaseNotificationHandler
from coeus.services.resource_admission import LocalResourceAdmissionController
from coeus.services.rfi_search import build_rfi_search_service
from coeus.services.routing import build_routing_service
from coeus.services.similar_requests import SimilarRequestService
from coeus.services.store_builder import build_store_services
from coeus.services.team_availability import TeamAvailabilityService, TeamCalendarService
from coeus.services.team_workspace import TeamWorkspaceService
from coeus.services.ticket_builder import build_provider_admission, build_ticket_services
from coeus.services.ticket_collaborators import TicketCollaboratorService
from coeus.services.ticket_lifecycle import TicketLifecycleService
from coeus.services.upload_admission import UploadAdmissionController
from coeus.services.voice_admission import VoiceSessionAdmission
from coeus.services.voice_models import VoiceModelService
from coeus.services.voice_sessions import VoiceSessionService


def configure_application_state(app: FastAPI, settings: Settings) -> None:
    """Assemble the local-first application through named responsibility groups."""
    app.state.settings = settings
    app.state.state_store = build_state_store(settings)
    app.state.integration_secret_store = EncryptedIntegrationSecretStore(
        app.state.state_store, settings
    )
    app.state.workflow_transaction = _workflow_transaction(app, settings)
    app.state.asset_token_service = AssetTokenService(settings.asset_token_secret)
    app.state.object_storage = build_object_storage(settings)
    app.state.admission_metrics = AdmissionMetrics()
    app.state.upload_admission = _upload_admission(settings, app.state.admission_metrics)
    app.state.search_admission = _search_admission(settings, app.state.admission_metrics)
    app.state.provider_admission = build_provider_admission(settings, app.state.admission_metrics)
    identity = configure_identity(app, settings)
    _configure_data_services(app, settings, identity)
    _configure_workflow_services(app, settings, identity)
    if settings.should_seed_demo():
        seed_demo_dataset(
            identity.access,
            app.state.store_services,
            app.state.object_storage,
            app.state.ticket_services,
            app.state.team_repository,
        )


def _upload_admission(settings: Settings, metrics: AdmissionMetrics) -> ResourceAdmission:
    if settings.environment in HOSTED_ENVIRONMENTS:
        return PostgresResourceAdmissionController(
            settings.database_url,
            resource_type="upload",
            max_concurrent=settings.upload_max_concurrent,
            max_concurrent_per_principal=settings.upload_max_concurrent_per_user,
            max_units=settings.upload_max_inflight_bytes,
            lease_seconds=300,
            mode=settings.shared_resource_admission_mode,
            metrics=metrics,
        )
    return UploadAdmissionController(
        max_concurrent=settings.upload_max_concurrent,
        max_per_user=settings.upload_max_concurrent_per_user,
        max_inflight_bytes=settings.upload_max_inflight_bytes,
        metrics=metrics,
    )


def _search_admission(settings: Settings, metrics: AdmissionMetrics) -> ResourceAdmission:
    if settings.environment in HOSTED_ENVIRONMENTS:
        return PostgresResourceAdmissionController(
            settings.database_url,
            resource_type="search",
            max_concurrent=settings.search_max_concurrent,
            max_concurrent_per_principal=settings.search_max_concurrent_per_principal,
            max_units=settings.search_max_concurrent,
            lease_seconds=70,
            mode=settings.shared_resource_admission_mode,
            metrics=metrics,
        )
    return LocalResourceAdmissionController(
        max_concurrent=settings.search_max_concurrent,
        max_concurrent_per_principal=settings.search_max_concurrent_per_principal,
        max_units=settings.search_max_concurrent,
        mode=settings.shared_resource_admission_mode,
        metrics=metrics,
    )


def _configure_data_services(
    app: FastAPI, settings: Settings, identity: IdentityComponents
) -> None:
    app.state.ai_model_service = AiModelService(
        settings,
        identity.audit_log,
        app.state.state_store,
        app.state.integration_secret_store,
    )
    app.state.voice_model_service = VoiceModelService(
        settings,
        identity.audit_log,
        app.state.state_store,
        app.state.integration_secret_store,
    )
    app.state.voice_session_admission = VoiceSessionAdmission(
        max_concurrent=settings.voice_session_max_concurrent,
        max_per_principal=settings.voice_session_max_per_principal,
        ttl_seconds=settings.voice_session_ttl_seconds,
    )
    app.state.voice_session_service = VoiceSessionService(
        settings,
        app.state.voice_model_service,
        app.state.voice_session_admission,
        identity.audit_log,
    )
    app.state.embedding_service = build_embedding_service(
        settings,
        app.state.ai_model_service,
        app.state.provider_admission,
    )
    app.state.ticket_services = build_ticket_services(
        settings,
        identity.audit_log,
        app.state.state_store,
        app.state.ai_model_service,
        app.state.workflow_transaction,
        app.state.admission_metrics,
        app.state.provider_admission,
    )
    app.state.store_services = build_store_services(
        identity.access,
        identity.audit_log,
        app.state.asset_token_service,
        app.state.state_store,
        app.state.embedding_service,
        app.state.ticket_services.tickets.assignment_snapshot,
    )
    configure_search_services(app, settings, identity.audit_log)
    app.state.admin_analytics_service = AdminAnalyticsService(
        identity.users,
        identity.registrations,
        identity.audit_log,
        app.state.ai_model_service,
        app.state.search_configuration_service,
        app.state.voice_model_service,
        app.state.admission_metrics,
    )
    app.state.ai_model_service.set_embedded_product_count_provider(
        app.state.store_services.repository.embedded_product_count
    )


def _configure_workflow_services(
    app: FastAPI, settings: Settings, identity: IdentityComponents
) -> None:
    tickets = app.state.ticket_services
    store = app.state.store_services
    audit_log = identity.audit_log
    app.state.team_repository = TeamRepository(app.state.state_store)
    seed_teams(app.state.team_repository, identity.users)
    app.state.ticket_collaborator_service = TicketCollaboratorService(
        users=identity.users,
        tickets=tickets.tickets,
        audit_log=audit_log,
    )
    app.state.ticket_lifecycle_service = TicketLifecycleService(
        tickets=tickets.tickets,
        audit_log=audit_log,
    )
    app.state.similar_request_service = SimilarRequestService(
        tickets,
        audit_log,
        app.state.embedding_service,
        app.state.search_index_repository,
        app.state.search_configuration_service,
        app.state.search_embedding_service,
    )
    app.state.rfi_search_service = build_rfi_search_service(
        tickets,
        store,
        identity.access,
        audit_log,
        app.state.embedding_service,
        app.state.grounded_search_service,
    )
    app.state.routing_service = build_routing_service(tickets, audit_log)
    app.state.jioc_routing_agent_service = JiocRoutingAgentService(tickets)
    app.state.manager_queue_service = ManagerQueueService(tickets)
    app.state.analyst_assignment_service = AnalystAssignmentService(
        tickets,
        identity.access,
        app.state.team_repository,
        audit_log,
    )
    app.state.analyst_workflow_service = AnalystWorkflowService(
        tickets,
        store,
        audit_log,
    )
    draft_policy = configure_product_workflow(
        app, settings, identity.access, app.state.team_repository
    )
    app.state.manager_approval_service = ManagerApprovalService(
        tickets, audit_log, app.state.team_repository, draft_policy
    )
    app.state.notification_service = NotificationService(
        audit_log,
        app.state.state_store,
        build_email_provider(settings),
    )
    app.state.quality_control_service = build_quality_control_service(
        tickets,
        store,
        identity.access,
        audit_log,
        app.state.object_storage,
        app.state.notification_service,
        app.state.team_repository,
        draft_policy,
        app.state.workflow_transaction,
    )
    if settings.environment in HOSTED_ENVIRONMENTS:
        app.state.outbox_dispatcher = OutboxDispatcher(
            PostgresOutboxStore(settings.database_url),
            {
                "ticket_shadow_changed": build_ticket_discovery_handler(app, identity.access),
                "product_release_notification": ProductReleaseNotificationHandler(
                    identity.users, app.state.notification_service
                ),
            },
            lease_seconds=settings.outbox_lease_seconds,
            retry_seconds=settings.outbox_retry_seconds,
            max_attempts=settings.outbox_max_attempts,
        )
    app.state.feedback_analytics_service = build_feedback_analytics_service(
        tickets,
        store,
        audit_log,
    )
    app.state.team_workspace_service = TeamWorkspaceService(
        app.state.team_repository,
        identity.users,
        audit_log,
    )
    app.state.team_availability_service = TeamAvailabilityService(
        app.state.team_repository,
        tickets,
    )
    app.state.team_calendar_service = TeamCalendarService(
        app.state.team_repository,
        audit_log,
    )


def _workflow_transaction(app: FastAPI, settings: Settings) -> PostgresWorkflowTransaction | None:
    state_store = app.state.state_store
    if isinstance(state_store, PostgresStateStore) and state_store.ticket_mode == "relational":
        return PostgresWorkflowTransaction(settings.database_url)
    return None
