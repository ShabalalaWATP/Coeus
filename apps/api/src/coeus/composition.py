from dataclasses import dataclass

from fastapi import FastAPI

from coeus.application.ports.admission import ResourceAdmission
from coeus.core.config import HOSTED_ENVIRONMENTS, Settings
from coeus.persistence.factory import build_audit_event_store, build_state_store
from coeus.persistence.outbox import PostgresOutboxStore
from coeus.persistence.state_store import PostgresStateStore
from coeus.persistence.workflow_transaction import PostgresWorkflowTransaction
from coeus.repositories.access import SeedAccessRepository
from coeus.repositories.acg_applications import AcgApplicationRepository
from coeus.repositories.auth import LoginAttemptRepository, SeedUserRepository, SessionRepository
from coeus.repositories.registration import RegistrationRepository
from coeus.repositories.teams import TeamRepository
from coeus.repositories.teams_seed import seed_teams
from coeus.services.access import build_access_services
from coeus.services.ai_models import AiModelService
from coeus.services.analyst_assignment_service import AnalystAssignmentService
from coeus.services.analyst_workflow import AnalystWorkflowService
from coeus.services.asset_tokens import AssetTokenService
from coeus.services.audit import AuditLog
from coeus.services.auth import AuthService
from coeus.services.demo_seed import seed_demo_dataset
from coeus.services.email_delivery import build_email_provider
from coeus.services.embeddings import build_embedding_service
from coeus.services.feedback_analytics import build_feedback_analytics_service
from coeus.services.manager_approval import ManagerApprovalService
from coeus.services.manager_queue import ManagerQueueService
from coeus.services.notifications import NotificationService
from coeus.services.object_storage import build_object_storage
from coeus.services.outbox_dispatcher import OutboxDispatcher
from coeus.services.passwords import PasswordHasher
from coeus.services.postgres_resource_admission import PostgresResourceAdmissionController
from coeus.services.quality_control import build_quality_control_service
from coeus.services.registration import RegistrationService
from coeus.services.release_notification_handler import ProductReleaseNotificationHandler
from coeus.services.resource_admission import LocalResourceAdmissionController
from coeus.services.rfi_search import build_rfi_search_service
from coeus.services.routing import build_routing_service
from coeus.services.similar_requests import SimilarRequestService
from coeus.services.store_builder import build_store_services
from coeus.services.team_availability import TeamAvailabilityService, TeamCalendarService
from coeus.services.team_workspace import TeamWorkspaceService
from coeus.services.ticket_builder import build_ticket_services
from coeus.services.ticket_collaborators import TicketCollaboratorService
from coeus.services.ticket_lifecycle import TicketLifecycleService
from coeus.services.upload_admission import UploadAdmissionController
from coeus.services.user_admin import UserAdminService


@dataclass(frozen=True)
class IdentityComponents:
    users: SeedUserRepository
    sessions: SessionRepository
    access: SeedAccessRepository
    login_attempts: LoginAttemptRepository
    password_hasher: PasswordHasher
    audit_log: AuditLog


def configure_application_state(app: FastAPI, settings: Settings) -> None:
    """Assemble the local-first application through named responsibility groups."""
    app.state.settings = settings
    app.state.state_store = build_state_store(settings)
    app.state.workflow_transaction = _workflow_transaction(app, settings)
    app.state.asset_token_service = AssetTokenService(settings.asset_token_secret)
    app.state.object_storage = build_object_storage(settings)
    app.state.upload_admission = _upload_admission(settings)
    app.state.search_admission = _search_admission(settings)
    identity = _configure_identity(app, settings)
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


def _upload_admission(settings: Settings) -> ResourceAdmission:
    if settings.environment in HOSTED_ENVIRONMENTS:
        return PostgresResourceAdmissionController(
            settings.database_url,
            resource_type="upload",
            max_concurrent=settings.upload_max_concurrent,
            max_concurrent_per_principal=settings.upload_max_concurrent_per_user,
            max_units=settings.upload_max_inflight_bytes,
            lease_seconds=300,
            mode=settings.shared_resource_admission_mode,
        )
    return UploadAdmissionController(
        max_concurrent=settings.upload_max_concurrent,
        max_per_user=settings.upload_max_concurrent_per_user,
        max_inflight_bytes=settings.upload_max_inflight_bytes,
    )


def _search_admission(settings: Settings) -> ResourceAdmission:
    if settings.environment in HOSTED_ENVIRONMENTS:
        return PostgresResourceAdmissionController(
            settings.database_url,
            resource_type="search",
            max_concurrent=settings.search_max_concurrent,
            max_concurrent_per_principal=settings.search_max_concurrent_per_principal,
            max_units=settings.search_max_concurrent,
            lease_seconds=70,
            mode=settings.shared_resource_admission_mode,
        )
    return LocalResourceAdmissionController(
        max_concurrent=settings.search_max_concurrent,
        max_concurrent_per_principal=settings.search_max_concurrent_per_principal,
        max_units=settings.search_max_concurrent,
        mode=settings.shared_resource_admission_mode,
    )


def _configure_identity(app: FastAPI, settings: Settings) -> IdentityComponents:
    password_hasher = PasswordHasher(settings)
    users = SeedUserRepository(settings, password_hasher, app.state.state_store)
    sessions = SessionRepository(app.state.state_store)
    access = SeedAccessRepository(users, app.state.state_store)
    audit_log = AuditLog(
        max_events=settings.audit_log_max_events,
        event_store=build_audit_event_store(settings, app.state.state_store),
    )
    login_attempts = LoginAttemptRepository(max_entries=settings.login_attempt_max_entries)
    app.state.auth_service = AuthService(
        settings=settings,
        users=users,
        sessions=sessions,
        login_attempts=login_attempts,
        password_hasher=password_hasher,
        audit_log=audit_log,
    )
    app.state.registration_service = RegistrationService(
        settings=settings,
        users=users,
        registrations=RegistrationRepository(app.state.state_store),
        password_hasher=password_hasher,
        audit_log=audit_log,
    )
    app.state.access_services = build_access_services(
        access,
        audit_log,
        AcgApplicationRepository(app.state.state_store),
    )
    app.state.user_admin_service = UserAdminService(
        users=users,
        sessions=sessions,
        login_attempts=login_attempts,
        password_hasher=password_hasher,
        audit_log=audit_log,
    )
    return IdentityComponents(users, sessions, access, login_attempts, password_hasher, audit_log)


def _configure_data_services(
    app: FastAPI, settings: Settings, identity: IdentityComponents
) -> None:
    app.state.ai_model_service = AiModelService(
        settings,
        identity.audit_log,
        app.state.state_store,
    )
    app.state.embedding_service = build_embedding_service(settings, app.state.ai_model_service)
    app.state.store_services = build_store_services(
        identity.access,
        identity.audit_log,
        app.state.asset_token_service,
        app.state.state_store,
        app.state.embedding_service,
    )
    app.state.ai_model_service.set_embedded_product_count_provider(
        app.state.store_services.repository.embedded_product_count
    )
    app.state.ticket_services = build_ticket_services(
        settings,
        identity.audit_log,
        app.state.state_store,
        app.state.ai_model_service,
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
        transaction=app.state.workflow_transaction,
    )
    app.state.similar_request_service = SimilarRequestService(
        tickets,
        audit_log,
        app.state.embedding_service,
    )
    app.state.rfi_search_service = build_rfi_search_service(
        tickets,
        store,
        identity.access,
        audit_log,
        app.state.embedding_service,
    )
    app.state.routing_service = build_routing_service(tickets, audit_log)
    app.state.manager_queue_service = ManagerQueueService(tickets)
    app.state.manager_approval_service = ManagerApprovalService(
        tickets, audit_log, app.state.team_repository
    )
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
    # Notifications are built before QC because the QC release step notifies
    # the requester when it publishes the approved product.
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
        app.state.workflow_transaction,
    )
    if settings.environment in HOSTED_ENVIRONMENTS:
        app.state.outbox_dispatcher = OutboxDispatcher(
            PostgresOutboxStore(settings.database_url),
            {
                "ticket_shadow_changed": lambda _message: None,
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
