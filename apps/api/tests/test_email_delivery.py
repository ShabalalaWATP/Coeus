from datetime import UTC, datetime
from email.message import EmailMessage
from uuid import uuid4

import pytest

from coeus.core.config import Settings
from coeus.core.permissions import Permission
from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.notifications import EmailRecord
from coeus.services import email_delivery
from coeus.services.audit import AuditEvent, AuditLog
from coeus.services.email_delivery import EmailDeliveryError, build_email_provider
from coeus.services.notifications import NotificationService


class RecordingEmailProvider:
    def __init__(self) -> None:
        self.sent: list[EmailRecord] = []

    def send(self, email: EmailRecord) -> None:
        self.sent.append(email)


class FailingEmailProvider:
    def send(self, _email: EmailRecord) -> None:
        raise EmailDeliveryError("SMTP failed.")


class ToggleStateStore:
    def __init__(self) -> None:
        self.fail_saves = False
        self.payloads: dict[str, dict[str, object]] = {}

    def load(self, namespace: str) -> dict[str, object] | None:
        return self.payloads.get(namespace)

    def save(self, namespace: str, payload: dict[str, object]) -> None:
        if self.fail_saves:
            raise RuntimeError("state store unavailable")
        self.payloads[namespace] = payload


class FailingAuditLog(AuditLog):
    def record(
        self,
        event_type: str,
        actor_user_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> AuditEvent:
        raise RuntimeError("audit unavailable")


def test_notification_service_delivers_email_to_configured_provider() -> None:
    audit_log = AuditLog()
    provider = RecordingEmailProvider()
    service = NotificationService(audit_log, email_provider=provider)

    email = service.record_email(_user(), "Release ready", "Open Istari.")

    assert provider.sent == [email]
    assert service.outbox_size() == 1
    assert _event_types(audit_log) == ["email_recorded"]


def test_notification_and_email_deduplicate_durable_outbox_retry() -> None:
    audit_log = AuditLog()
    provider = RecordingEmailProvider()
    service = NotificationService(audit_log, email_provider=provider)
    user = _user()
    event_id = uuid4()

    first_notification = service.notify(
        user, "release", "Release ready", "Open Istari.", notification_id=event_id
    )
    first_email = service.record_email(user, "Release ready", "Open Istari.", email_id=event_id)
    retried_notification = service.notify(
        user, "release", "Release ready", "Open Istari.", notification_id=event_id
    )
    retried_email = service.record_email(user, "Release ready", "Open Istari.", email_id=event_id)

    assert retried_notification is first_notification
    assert retried_email is first_email
    assert service.list_for_user(user) == (first_notification,)
    assert service.outbox_size() == 1
    assert provider.sent == [first_email]
    assert _event_types(audit_log) == ["email_recorded"]


def test_notification_service_audits_email_delivery_failure() -> None:
    audit_log = AuditLog()
    service = NotificationService(audit_log, email_provider=FailingEmailProvider())

    service.record_email(_user(), "Release ready", "Open Istari.")

    assert _event_types(audit_log) == ["email_recorded", "email_delivery_failed"]


def test_notification_creation_rolls_back_when_persistence_fails() -> None:
    state_store = ToggleStateStore()
    service = NotificationService(AuditLog(), state_store=state_store)
    user = _user()

    state_store.fail_saves = True
    with pytest.raises(RuntimeError, match="state store unavailable"):
        service.notify(user, "release", "Release ready", "Open Istari.")

    assert service.list_for_user(user) == ()


def test_notification_mark_read_rolls_back_when_persistence_fails() -> None:
    state_store = ToggleStateStore()
    service = NotificationService(AuditLog(), state_store=state_store)
    user = _user()
    notification = service.notify(user, "release", "Release ready", "Open Istari.")

    state_store.fail_saves = True
    with pytest.raises(RuntimeError, match="state store unavailable"):
        service.mark_read(user, notification.notification_id)

    assert service.list_for_user(user)[0].read is False


def test_email_outbox_rolls_back_when_audit_fails() -> None:
    service = NotificationService(FailingAuditLog())

    with pytest.raises(RuntimeError, match="audit unavailable"):
        service.record_email(_user(), "Release ready", "Open Istari.")

    assert service.outbox_size() == 0


def test_smtp_runtime_config_requires_host_and_sender() -> None:
    settings = Settings(email_provider="smtp")

    with pytest.raises(ValueError, match="COEUS_SMTP_HOST"):
        settings.require_runtime_security()


def test_smtp_runtime_config_allows_local_sender() -> None:
    settings = Settings(
        email_provider="smtp",
        smtp_host="localhost",
        smtp_from="noreply@example.test",
    )

    settings.require_runtime_security()


def test_smtp_provider_sends_message(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeSmtp:
        def __init__(self, host: str, port: int, timeout: int) -> None:
            captured["connect"] = (host, port, timeout)

        def __enter__(self) -> "FakeSmtp":
            return self

        def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
            return None

        def starttls(self, context: object) -> None:
            captured["starttls"] = context

        def login(self, username: str, password: str) -> None:
            captured["login"] = (username, password)

        def send_message(self, message: EmailMessage) -> None:
            captured["subject"] = message["Subject"]

    monkeypatch.setattr(email_delivery, "SMTP", FakeSmtp)
    provider = build_email_provider(
        Settings(
            email_provider="smtp",
            smtp_host="localhost",
            smtp_from="noreply@example.test",
            smtp_username="user",
            smtp_password=_smtp_password(),
            smtp_timeout_seconds=5,
        )
    )

    provider.send(
        EmailRecord(uuid4(), "user@example.test", "Release ready", "Open Istari.", _now())
    )

    assert captured["connect"] == ("localhost", 587, 5)
    assert captured["login"] == ("user", _smtp_password())
    assert captured["subject"] == "Release ready"
    assert "starttls" in captured


def test_smtp_provider_wraps_delivery_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingSmtp:
        def __init__(self, _host: str, _port: int, timeout: int) -> None:
            raise OSError("offline")

    monkeypatch.setattr(email_delivery, "SMTP", FailingSmtp)
    provider = build_email_provider(
        Settings(email_provider="smtp", smtp_host="localhost", smtp_from="noreply@example.test")
    )

    with pytest.raises(EmailDeliveryError):
        provider.send(
            EmailRecord(uuid4(), "user@example.test", "Release ready", "Open Istari.", _now())
        )


def test_smtp_provider_can_send_without_tls_or_authentication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    class PlainSmtp:
        def __init__(self, _host: str, _port: int, timeout: int) -> None:
            return None

        def __enter__(self) -> "PlainSmtp":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def send_message(self, _message: EmailMessage) -> None:
            calls.append("sent")

    monkeypatch.setattr(email_delivery, "SMTP", PlainSmtp)
    provider = build_email_provider(
        Settings(
            email_provider="smtp",
            smtp_host="localhost",
            smtp_from="noreply@example.test",
            smtp_starttls=False,
        )
    )

    provider.send(EmailRecord(uuid4(), "user@example.test", "Subject", "Body", _now()))

    assert calls == ["sent"]


def _user() -> UserAccount:
    return UserAccount(
        user_id=uuid4(),
        username="user@example.test",
        display_name="Example User",
        roles=frozenset({RoleName.USER}),
        permissions=frozenset({Permission.TICKET_CREATE}),
        password_hash="",
        is_active=True,
        clearance_level=1,
    )


def _event_types(audit_log: AuditLog) -> list[str]:
    return [event.event_type for event in audit_log.list_events()]


def _now() -> datetime:
    return datetime.now(UTC)


def _smtp_password() -> str:
    return "smtp-password-for-test"
