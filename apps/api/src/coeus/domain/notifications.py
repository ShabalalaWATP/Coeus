from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class NotificationRecord:
    notification_id: UUID
    user_id: UUID
    kind: str
    title: str
    body: str
    link_path: str | None
    read: bool
    created_at: datetime


@dataclass(frozen=True)
class EmailRecord:
    email_id: UUID
    to_username: str
    subject: str
    body: str
    created_at: datetime
