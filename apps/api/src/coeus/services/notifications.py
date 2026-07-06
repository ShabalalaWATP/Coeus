from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from coeus.core.errors import AppError
from coeus.domain.auth import UserAccount
from coeus.domain.notifications import EmailRecord, NotificationRecord
from coeus.services.audit import AuditLog

MAX_NOTIFICATIONS_PER_USER = 200


class NotificationService:
    """In-app notifications plus a recorded email outbox.

    Locally no SMTP relay exists, so emails are recorded and audited rather
    than transmitted; deployed environments attach a real delivery provider.
    """

    def __init__(self, audit_log: AuditLog) -> None:
        self._audit_log = audit_log
        self._notifications: dict[UUID, list[NotificationRecord]] = {}
        self._outbox: list[EmailRecord] = []

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
        existing = self._notifications.setdefault(user.user_id, [])
        existing.append(record)
        del existing[:-MAX_NOTIFICATIONS_PER_USER]
        return record

    def record_email(self, user: UserAccount, subject: str, body: str) -> EmailRecord:
        email = EmailRecord(
            email_id=uuid4(),
            to_username=user.username,
            subject=subject,
            body=body,
            created_at=datetime.now(UTC),
        )
        self._outbox.append(email)
        del self._outbox[:-MAX_NOTIFICATIONS_PER_USER]
        self._audit_log.record(
            "email_recorded",
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
                records[index] = updated
                return updated
        raise AppError(404, "notification_not_found", "Notification was not found.")

    def outbox_size(self) -> int:
        return len(self._outbox)
