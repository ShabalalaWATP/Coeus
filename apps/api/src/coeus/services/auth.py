from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from secrets import compare_digest, token_urlsafe

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import AuthenticatedSession, SessionRecord, UserAccount
from coeus.repositories.auth import LoginAttemptRepository, SeedUserRepository, SessionRepository
from coeus.services.audit import AuditLog
from coeus.services.passwords import PasswordHasher

AUTHENTICATION_FAILED = "Authentication failed."
DUMMY_LOGIN_HASH_INPUT = "coeus-unknown-user"


@dataclass(frozen=True)
class LoginResult:
    user: UserAccount
    session: SessionRecord
    default_route: str


class AuthService:
    def __init__(
        self,
        settings: Settings,
        users: SeedUserRepository,
        sessions: SessionRepository,
        login_attempts: LoginAttemptRepository,
        password_hasher: PasswordHasher,
        audit_log: AuditLog,
    ) -> None:
        self._settings = settings
        self._users = users
        self._sessions = sessions
        self._login_attempts = login_attempts
        self._password_hasher = password_hasher
        self._audit_log = audit_log
        self._unknown_user_password_hash = password_hasher.hash(DUMMY_LOGIN_HASH_INPUT)

    def login(
        self, username: str, credential: str, replace_session_id: str | None = None
    ) -> LoginResult:
        self._reject_if_locked(username)
        user = self._users.get_by_username(username)
        password_hash = user.password_hash if user is not None else self._unknown_user_password_hash
        password_valid = self._password_hasher.verify(password_hash, credential)
        if user is None or not password_valid:
            self._record_login_failure(username, user)
        if user is None:
            raise self._auth_failed()
        if not user.is_active:
            self._audit_log.record("login_failure", str(user.user_id), {"reason": "user_disabled"})
            raise self._auth_failed()
        if replace_session_id is not None:
            self._sessions.delete(replace_session_id)
        self._login_attempts.reset(username)
        session = self._create_session(user)
        self._audit_log.record("login_success", str(user.user_id))
        from coeus.domain.rbac import default_route_for_roles

        return LoginResult(
            user=user,
            session=session,
            default_route=default_route_for_roles(user.roles),
        )

    def logout(self, session_id: str) -> None:
        authenticated = self.require_session(session_id)
        self._sessions.delete(session_id)
        self._audit_log.record("logout", str(authenticated.user.user_id))

    def require_session(self, session_id: str | None) -> AuthenticatedSession:
        if session_id is None or session_id == "":
            raise AppError(401, "not_authenticated", "Authentication is required.")
        session = self._sessions.get(session_id)
        if session is None:
            raise AppError(401, "not_authenticated", "Authentication is required.")
        if session.expires_at <= datetime.now(UTC):
            self._sessions.delete(session.session_id)
            raise AppError(401, "session_expired", "Session expired.")
        user = self._users.get_by_id(session.user_id)
        if user is None or not user.is_active:
            self._sessions.delete(session.session_id)
            raise AppError(401, "not_authenticated", "Authentication is required.")
        return AuthenticatedSession(session=session, user=user)

    def require_csrf(
        self, authenticated: AuthenticatedSession, submitted_token: str | None
    ) -> None:
        if submitted_token is None or not compare_digest(
            submitted_token,
            authenticated.session.csrf_token,
        ):
            raise AppError(403, "csrf_failed", "CSRF validation failed.")

    def require_permission(
        self,
        authenticated: AuthenticatedSession,
        permission: Permission,
    ) -> None:
        if permission not in authenticated.user.permissions:
            raise AppError(403, "forbidden", "Permission denied.")

    def rotate_session(self, session_id: str) -> SessionRecord:
        authenticated = self.require_session(session_id)
        self._sessions.delete(session_id)
        return self._create_session(authenticated.user)

    @property
    def audit_log(self) -> AuditLog:
        return self._audit_log

    def _create_session(self, user: UserAccount) -> SessionRecord:
        now = datetime.now(UTC)
        session = SessionRecord(
            session_id=token_urlsafe(32),
            user_id=user.user_id,
            csrf_token=token_urlsafe(32),
            created_at=now,
            expires_at=now + timedelta(seconds=self._settings.session_ttl_seconds),
        )
        self._sessions.save(session)
        return session

    def _reject_if_locked(self, username: str) -> None:
        locked_until = self._login_attempts.get_lockout_until(username)
        if locked_until is not None and locked_until > datetime.now(UTC):
            self._audit_log.record("login_failure", None, {"reason": "account_locked"})
            raise AppError(423, "account_locked", "Authentication temporarily locked.")
        if locked_until is not None:
            self._login_attempts.reset(username)

    def _record_login_failure(self, username: str, user: UserAccount | None) -> None:
        locked_until = self._login_attempts.record_failure(
            username,
            self._settings.login_lockout_threshold,
            self._settings.login_lockout_seconds,
        )
        metadata = {"reason": "invalid_credentials"}
        if locked_until is not None:
            metadata["locked_until"] = locked_until.isoformat()
        self._audit_log.record(
            "login_failure",
            str(user.user_id) if user is not None else None,
            metadata,
        )
        raise self._auth_failed()

    @staticmethod
    def _auth_failed() -> AppError:
        return AppError(401, "authentication_failed", AUTHENTICATION_FAILED)
