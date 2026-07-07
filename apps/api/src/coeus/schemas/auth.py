from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(
        min_length=1,
        max_length=256,
        validation_alias="currentPassword",
    )
    # Same policy as registration passwords.
    new_password: str = Field(
        min_length=12,
        max_length=256,
        validation_alias="newPassword",
    )


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: UUID = Field(serialization_alias="id")
    username: str
    display_name: str = Field(serialization_alias="displayName")
    roles: list[str]
    permissions: list[str]
    default_route: str = Field(serialization_alias="defaultRoute")
    password_reset_required: bool = Field(
        default=False,
        serialization_alias="passwordResetRequired",
    )


class AuthSessionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    user: UserProfileResponse
    csrf_token: str = Field(serialization_alias="csrfToken")


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str = Field(serialization_alias="eventId")
    event_type: str = Field(serialization_alias="eventType")
    occurred_at: datetime = Field(serialization_alias="occurredAt")
    actor_user_id: str | None = Field(serialization_alias="actorUserId")
    metadata: dict[str, str]


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    events: list[AuditEventResponse]
