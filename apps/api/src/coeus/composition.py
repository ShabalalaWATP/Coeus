from dataclasses import dataclass

from fastapi import FastAPI

from coeus.core.config import Settings
from coeus.persistence.factory import build_audit_event_store, build_state_store
from coeus.repositories.access import SeedAccessRepository
from coeus.repositories.auth import LoginAttemptRepository, SeedUserRepository, SessionRepository
from coeus.repositories.registration import RegistrationRepository
from coeus.services.access import build_access_services
from coeus.services.ai_models import AiModelService
from coeus.services.analyst_workflow import AnalystWorkflowService
from coeus.services.asset_tokens import AssetTokenService
from coeus.services.audit import AuditLog
from coeus.services.auth import AuthService
from coeus.services.email_delivery import build_email_provider
from coeus.services.embeddings import build_embedding_service
from coeus.services.feedback_analytics import build_feedback_analytics_service
from coeus.services.notifications import NotificationService
from coeus.services.object_storage import build_object_storage, seed_store_asset_placeholders
from coeus.services.passwords import PasswordHasher
from coeus.services.product_release import ProductReleaseService
from coeus.services.quality_control import build_quality_control_service
from coeus.services.registration import RegistrationService
from coeus.services.rfi_search import build_rfi_search_service
from coeus.services.routing import build_routing_service
from coeus.services.similar_requests import SimilarRequestService
from coeus.services.store_builder import build_store_services
from coeus.services.ticket_builder import build_ticket_services
from coeus.services.ticket_collaborators import TicketCollaboratorService
from coeus.services.ticket_lifecycle import TicketLifecycleService
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
    app.state.asset_token_service = AssetTokenService(settings.asset_token_secret)
    app.state.object_storage = build_object_storage(settings)
    identity = _configure_identity(app, settings)
    _configure_data_services(app, settings, identity)
    _configure_workflow_services(app, settings, identity)


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
    app.state.access_services = build_access_services(access, audit_log)
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
    seed_store_asset_placeholders(
        app.state.object_storage,
        app.state.store_services.repository.list_products(),
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
    )
    app.state.rfi_search_service = build_rfi_search_service(
        tickets,
        store,
        identity.access,
        audit_log,
        app.state.embedding_service,
    )
    app.state.routing_service = build_routing_service(tickets, audit_log)
    app.state.analyst_workflow_service = AnalystWorkflowService(
        tickets,
        store,
        identity.access,
        audit_log,
    )
    app.state.quality_control_service = build_quality_control_service(
        tickets,
        store,
        identity.access,
        audit_log,
        app.state.object_storage,
    )
    app.state.notification_service = NotificationService(
        audit_log,
        app.state.state_store,
        build_email_provider(settings),
    )
    app.state.product_release_service = ProductReleaseService(
        tickets=tickets,
        store=store,
        access=identity.access,
        notifications=app.state.notification_service,
        audit_log=audit_log,
    )
    app.state.feedback_analytics_service = build_feedback_analytics_service(
        tickets,
        store,
        audit_log,
    )
