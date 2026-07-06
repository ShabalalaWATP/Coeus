from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NotificationResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    notification_id: UUID = Field(serialization_alias="id")
    kind: str
    title: str
    body: str
    link_path: str | None = Field(serialization_alias="linkPath")
    read: bool
    created_at: datetime = Field(serialization_alias="createdAt")


class NotificationListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    notifications: list[NotificationResponse]
    unread: int
