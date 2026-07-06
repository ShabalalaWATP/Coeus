from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: UUID = Field(serialization_alias="id")
    username: str
    display_name: str = Field(serialization_alias="displayName")
    roles: list[str]
    clearance_level: int = Field(serialization_alias="clearanceLevel")
    is_active: bool = Field(serialization_alias="isActive")


class AdminUserListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    users: list[AdminUserResponse]


class UserRolesRequest(BaseModel):
    roles: list[str] = Field(min_length=1, max_length=8)


class UserClearanceRequest(BaseModel):
    clearance_level: int = Field(ge=1, le=5, validation_alias="clearanceLevel")


class UserStatusRequest(BaseModel):
    is_active: bool = Field(validation_alias="isActive")
