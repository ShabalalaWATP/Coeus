"""Application composition for identity, authentication and access services."""

from dataclasses import dataclass

from fastapi import FastAPI

from coeus.core.config import Settings
from coeus.persistence.factory import build_audit_event_store
from coeus.repositories.access import SeedAccessRepository
from coeus.repositories.acg_applications import AcgApplicationRepository
from coeus.repositories.auth import LoginAttemptRepository, SeedUserRepository, SessionRepository
from coeus.repositories.registration import RegistrationRepository
from coeus.services.access import build_access_services
from coeus.services.audit import AuditLog
from coeus.services.auth import AuthService
from coeus.services.passwords import PasswordHasher
from coeus.services.registration import RegistrationService
from coeus.services.user_admin import UserAdminService


@dataclass(frozen=True)
class IdentityComponents:
    users: SeedUserRepository
    sessions: SessionRepository
    access: SeedAccessRepository
    login_attempts: LoginAttemptRepository
    password_hasher: PasswordHasher
    audit_log: AuditLog
    registrations: RegistrationRepository


def configure_identity(app: FastAPI, settings: Settings) -> IdentityComponents:
    password_hasher = PasswordHasher(settings)
    users = SeedUserRepository(settings, password_hasher, app.state.state_store)
    sessions = SessionRepository(
        app.state.state_store,
        max_per_user=settings.session_max_per_user,
        max_entries=settings.session_max_entries,
    )
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
    registrations = RegistrationRepository(app.state.state_store)
    app.state.registration_service = RegistrationService(
        settings=settings,
        users=users,
        registrations=registrations,
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
    return IdentityComponents(
        users, sessions, access, login_attempts, password_hasher, audit_log, registrations
    )
