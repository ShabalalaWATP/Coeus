from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import compare_digest, token_urlsafe
from typing import NoReturn

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.core.permissions import Permission
from coeus.domain.auth import AuthenticatedSession, SessionRecord, UserAccount
from coeus.repositories.auth import (
    AttemptStoreFull,
    IpAttemptRepository,
    LoginAttemptRepository,
    SeedUserRepository,
    SessionRepository,
    SessionStoreFull,
)
from coeus.services.audit import AuditLog
from coeus.services.passwords import PasswordHasher

AUTHENTICATION_FAILED = "Authentication failed."
DUMMY_LOGIN_HASH_INPUT = "coeus-unknown-user"


def hash_session_id(session_id: str) -> str:
    """Session identifiers are stored hashed so a state-file or database backup
    cannot be replayed to hijack a live session."""
    return sha256(session_id.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LoginResult:
    user: UserAccount
    session: SessionRecord
    default_route: str
    # Raw cookie value; only the SHA-256 hash is retained server-side.
    session_token: str


class AuthService:
    def __init__(
        self,
        settings: Settings,
        users: SeedUserRepository,
        sessions: SessionRepository,
        login_attempts: LoginAttemptRepository,
        password_hasher: PasswordHasher,
        audit_log: AuditLog,
        ip_attempts: IpAttemptRepository | None = None,
    ) -> None:
        self._settings = settings
        self._users = users
        self._sessions = sessions
        self._login_attempts = login_attempts
        self._ip_attempts = ip_attempts or IpAttemptRepository(
            max_entries=settings.auth_ip_max_entries
        )
        self._password_hasher = password_hasher
        self._audit_log = audit_log
        self._unknown_user_password_hash = password_hasher.hash(DUMMY_LOGIN_HASH_INPUT)

    def login(
        self,
        username: str,
        credential: str,
        replace_session_id: str | None = None,
        client_ip: str | None = None,
    ) -> LoginResult:
        self.throttle_source(client_ip)
        self._reject_if_locked(username)
        user = self._users.get_by_username(username)
        password_hash = user.password_hash if user is not None else self._unknown_user_password_hash
        password_valid = self._password_hasher.verify(password_hash, credential)
        if user is None or not password_valid:
            self._record_login_failure(username, user)
        if not user.is_active:
            self._audit_log.record("login_failure", str(user.user_id), {"reason": "user_disabled"})
            raise self._auth_failed()
        attempts_reset = None
        replaced_session: SessionRecord | None = None
        if replace_session_id is not None:
            replaced_session = self._sessions.get(hash_session_id(replace_session_id))
        new_session: SessionRecord | None = None
        try:
            if replace_session_id is not None:
                self._sessions.delete(hash_session_id(replace_session_id))
            attempts_reset = self._login_attempts.reset(username)
            session_token, session = self._create_session(user)
            new_session = session
            current_user = self._users.get_by_id(user.user_id)
            if (
                current_user is None
                or not current_user.is_active
                or current_user.credential_version != user.credential_version
                or current_user.password_hash != user.password_hash
            ):
                raise self._auth_failed()
            self._audit_log.record("login_success", str(user.user_id))
        except Exception:
            if new_session is not None:
                self._sessions.delete(new_session.session_id)
            if replaced_session is not None:
                self._sessions.save(replaced_session)
            if attempts_reset is not None:
                self._login_attempts.restore_reset(username, attempts_reset)
            raise
        from coeus.domain.rbac import default_route_for_roles

        return LoginResult(
            user=user,
            session=session,
            default_route=default_route_for_roles(user.roles),
            session_token=session_token,
        )

    def logout(self, session_id: str) -> None:
        authenticated = self.require_session(session_id)
        deleted = self._sessions.delete(authenticated.session.session_id)
        if deleted is None:
            raise AppError(401, "not_authenticated", "Authentication is required.")
        self._audit_log.record("logout", str(authenticated.user.user_id))

    def require_session(self, session_id: str | None) -> AuthenticatedSession:
        if session_id is None or session_id == "":
            raise AppError(401, "not_authenticated", "Authentication is required.")
        session = self._sessions.get(hash_session_id(session_id))
        if session is None:
            raise AppError(401, "not_authenticated", "Authentication is required.")
        if session.expires_at <= datetime.now(UTC):
            self._sessions.delete(session.session_id)
            raise AppError(401, "session_expired", "Session expired.")
        user = self._users.get_by_id(session.user_id)
        if user is None or not user.is_active:
            self._sessions.delete(session.session_id)
            raise AppError(401, "not_authenticated", "Authentication is required.")
        if session.credential_version != user.credential_version:
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

    def rotate_session(self, session_id: str) -> tuple[str, SessionRecord]:
        authenticated = self.require_session(session_id)
        session_token, replacement = self._prepare_session(authenticated.user)
        if not self._sessions.replace_if_current(
            authenticated.session.session_id,
            replacement,
        ):
            raise AppError(401, "not_authenticated", "Authentication is required.")
        return session_token, replacement

    def change_password(
        self, session_id: str | None, current_password: str, new_password: str
    ) -> LoginResult:
        authenticated = self.require_session(session_id)
        user = authenticated.user
        if not self._password_hasher.verify(user.password_hash, current_password):
            self._audit_log.record(
                "password_change_failed",
                str(user.user_id),
                {"reason": "invalid_current_password"},
            )
            raise AppError(403, "invalid_current_password", "Current password is incorrect.")
        updated = replace(
            user,
            password_hash=self._password_hasher.hash(new_password),
            password_reset_required=False,
            credential_version=user.credential_version + 1,
        )
        session_token: str
        session: SessionRecord | None = None

        def confirm_change() -> None:
            nonlocal session_token, session
            revoked_sessions = self._sessions.delete_for_user(user.user_id)
            attempts_reset = self._login_attempts.reset(user.username)
            try:
                session_token, session = self._create_session(updated)
                self._audit_log.record("password_changed", str(user.user_id))
            except Exception:
                if session is not None:
                    self._sessions.delete(session.session_id)
                for revoked_session in revoked_sessions:
                    self._sessions.save(revoked_session)
                self._login_attempts.restore_reset(user.username, attempts_reset)
                raise

        changed = self._users.save_if_current_with_confirmation(user, updated, confirm_change)
        if not changed or session is None:
            raise self._auth_failed()
        from coeus.domain.rbac import default_route_for_roles

        return LoginResult(
            user=updated,
            session=session,
            default_route=default_route_for_roles(updated.roles),
            session_token=session_token,
        )

    @property
    def audit_log(self) -> AuditLog:
        return self._audit_log

    def _create_session(self, user: UserAccount) -> tuple[str, SessionRecord]:
        session_token, session = self._prepare_session(user)
        try:
            self._sessions.save(session)
        except SessionStoreFull as exc:
            self._audit_log.record(
                "auth_throttled",
                str(user.user_id),
                {"reason": "session_capacity_unavailable"},
            )
            raise AppError(
                503,
                "session_capacity_unavailable",
                "Authentication is temporarily unavailable.",
            ) from exc
        return session_token, session

    def _prepare_session(self, user: UserAccount) -> tuple[str, SessionRecord]:
        now = datetime.now(UTC)
        session_token = token_urlsafe(32)
        session = SessionRecord(
            session_id=hash_session_id(session_token),
            user_id=user.user_id,
            csrf_token=token_urlsafe(32),
            created_at=now,
            expires_at=now + timedelta(seconds=self._settings.session_ttl_seconds),
            credential_version=user.credential_version,
        )
        return session_token, session

    def throttle_source(self, client_ip: str | None) -> None:
        """Reject authentication attempts from sources over their budget.

        Applied to login and registration so a single source cannot spray many
        usernames without ever tripping a per-username lockout.
        """
        if client_ip is None:
            return
        within = self._ip_attempts.within_budget(
            client_ip,
            self._settings.auth_ip_max_attempts,
            self._settings.auth_ip_window_seconds,
        )
        if not within:
            self._audit_log.record("auth_throttled", None, {"reason": "ip_budget_exceeded"})
            raise AppError(429, "too_many_attempts", "Too many attempts. Try again later.")

    def _reject_if_locked(self, username: str) -> None:
        locked_until = self._login_attempts.active_lockout_until(username)
        if locked_until is not None:
            self._audit_log.record("login_failure", None, {"reason": "account_locked"})
            raise AppError(423, "account_locked", "Authentication temporarily locked.")

    def _record_login_failure(self, username: str, user: UserAccount | None) -> NoReturn:
        try:
            locked_until = self._login_attempts.record_failure(
                username,
                self._settings.login_lockout_threshold,
                self._settings.login_lockout_seconds,
            )
        except AttemptStoreFull as exc:
            self._audit_log.record("auth_throttled", None, {"reason": "attempt_store_full"})
            raise AppError(429, "too_many_attempts", "Too many attempts. Try again later.") from exc
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
