from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from coeus.core.errors import AppError
from coeus.domain.auth import UserAccount
from coeus.domain.notifications import EmailRecord, NotificationRecord
from coeus.persistence.codec import decode_value, encode_value
from coeus.persistence.state_store import StateStore
from coeus.services.audit import AuditLog
from coeus.services.email_delivery import EmailDeliveryError, EmailProvider, OutboxEmailProvider

MAX_NOTIFICATIONS_PER_USER = 200


class NotificationService:
    """In-app notifications plus a bounded email outbox."""

    def __init__(
        self,
        audit_log: AuditLog,
        state_store: StateStore | None = None,
        email_provider: EmailProvider | None = None,
    ) -> None:
        self._audit_log = audit_log
        self._state_store = state_store
        self._email_provider = email_provider or OutboxEmailProvider()
        self._notifications: dict[UUID, list[NotificationRecord]] = {}
        self._outbox: list[EmailRecord] = []
        self._restore_or_persist()

    def notify(
        self,
        user: UserAccount,
        kind: str,
        title: str,
        body: str,
        link_path: str | None = None,
    ) -> NotificationRecord:
        record = NotificationRecord(
            notification_id=uuid4(),
            user_id=user.user_id,
            kind=kind,
            title=title,
            body=body,
            link_path=link_path,
            read=False,
            created_at=datetime.now(UTC),
        )
        snapshot = tuple(self._notifications.get(user.user_id, ()))
        try:
            existing = self._notifications.setdefault(user.user_id, [])
            existing.append(record)
            del existing[:-MAX_NOTIFICATIONS_PER_USER]
            self._persist()
        except Exception:
            self._restore_user_notifications(user.user_id, snapshot)
            raise
        return record

    def record_email(self, user: UserAccount, subject: str, body: str) -> EmailRecord:
        outbox_snapshot = tuple(self._outbox)
        email = EmailRecord(
            email_id=uuid4(),
            to_username=user.username,
            subject=subject,
            body=body,
            created_at=datetime.now(UTC),
        )
        try:
            self._outbox.append(email)
            del self._outbox[:-MAX_NOTIFICATIONS_PER_USER]
            self._persist()
            self._audit_log.record(
                "email_recorded",
                None,
                {"to_user_id": str(user.user_id), "subject": subject},
            )
        except Exception:
            self._outbox = list(outbox_snapshot)
            self._persist()
            raise
        try:
            self._email_provider.send(email)
        except EmailDeliveryError:
            self._audit_log.record(
                "email_delivery_failed",
                None,
                {"to_user_id": str(user.user_id), "subject": subject},
            )
        return email

    def list_for_user(self, actor: UserAccount) -> tuple[NotificationRecord, ...]:
        return tuple(reversed(self._notifications.get(actor.user_id, [])))

    def mark_read(self, actor: UserAccount, notification_id: UUID) -> NotificationRecord:
        records = self._notifications.get(actor.user_id, [])
        for index, record in enumerate(records):
            if record.notification_id == notification_id:
                updated = replace(record, read=True)
                snapshot = tuple(records)
                try:
                    records[index] = updated
                    self._persist()
                except Exception:
                    self._restore_user_notifications(actor.user_id, snapshot)
                    raise
                return updated
        raise AppError(404, "notification_not_found", "Notification was not found.")

    def outbox_size(self) -> int:
        return len(self._outbox)

    def _restore_or_persist(self) -> None:
        if self._state_store is None:
            return
        payload = self._state_store.load("notifications")
        if payload is None:
            self._persist()
            return
        records = tuple(decode_value(item) for item in payload.get("records", []))
        self._notifications = {}
        for record in records:
            self._notifications.setdefault(record.user_id, []).append(record)
        self._outbox = [decode_value(item) for item in payload.get("outbox", [])]

    def _persist(self) -> None:
        if self._state_store is None:
            return
        records = [
            record
            for user_records in self._notifications.values()
            for record in user_records[-MAX_NOTIFICATIONS_PER_USER:]
        ]
        self._state_store.save(
            "notifications",
            {
                "records": [encode_value(record) for record in records],
                "outbox": [encode_value(email) for email in self._outbox],
            },
        )

    def _restore_user_notifications(
        self, user_id: UUID, snapshot: tuple[NotificationRecord, ...]
    ) -> None:
        if snapshot:
            self._notifications[user_id] = list(snapshot)
        else:
            self._notifications.pop(user_id, None)
