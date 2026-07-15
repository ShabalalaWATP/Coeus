from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from coeus.domain.access import AcgApplicationStatus


class DirectoryUserResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: UUID = Field(serialization_alias="id")
    display_name: str = Field(serialization_alias="displayName")
    username: str


class AccessControlGroupResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    acg_id: UUID = Field(serialization_alias="id")
    code: str
    name: str
    description: str
    owner_user_id: UUID | None = Field(serialization_alias="ownerUserId")
    is_active: bool = Field(serialization_alias="isActive")
    member_user_ids: list[UUID] = Field(serialization_alias="memberUserIds")
    members: list[DirectoryUserResponse]


class AccessControlGroupListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    acgs: list[AccessControlGroupResponse]


class CreateAccessControlGroupRequest(BaseModel):
    code: str = Field(min_length=3, max_length=64)
    name: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=1, max_length=500)
    owner_user_id: UUID | None = Field(default=None, validation_alias="ownerUserId")


class UpdateAccessControlGroupRequest(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=120)
    description: str | None = Field(default=None, min_length=1, max_length=500)
    is_active: bool | None = Field(default=None, validation_alias="isActive")


class AddAccessControlGroupMemberRequest(BaseModel):
    user_id: UUID = Field(validation_alias="userId")


class AccessDiagnosticsRequest(BaseModel):
    user_id: UUID = Field(validation_alias="userId")


class AccessCheckResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    passed: bool
    reason: str


class AccessDiagnosticsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    allowed: bool
    reason: str
    checks: list[AccessCheckResponse]


class AcgCatalogueItemResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    acg_id: UUID = Field(serialization_alias="id")
    code: str
    name: str
    description: str
    is_member: bool = Field(serialization_alias="isMember")
    application_status: AcgApplicationStatus | None = Field(serialization_alias="applicationStatus")
    application_id: UUID | None = Field(serialization_alias="applicationId")
    can_review_applications: bool = Field(serialization_alias="canReviewApplications")
    can_manage_admins: bool = Field(serialization_alias="canManageAdmins")
    manager_names: list[str] = Field(serialization_alias="managerNames")


class AcgCatalogueResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    acgs: list[AcgCatalogueItemResponse]
    page: int
    page_size: int = Field(serialization_alias="pageSize")
    total: int
    total_pages: int = Field(serialization_alias="totalPages")


class SubmitAcgApplicationRequest(BaseModel):
    justification: str = Field(min_length=10, max_length=500)

    @field_validator("justification")
    @classmethod
    def strip_and_validate_justification(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 10:
            raise ValueError("Justification must contain at least 10 non-whitespace characters.")
        return stripped


class AcgApplicationResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    application_id: UUID = Field(serialization_alias="id")
    acg_id: UUID = Field(serialization_alias="acgId")
    acg_code: str = Field(serialization_alias="acgCode")
    acg_name: str = Field(serialization_alias="acgName")
    applicant_user_id: UUID = Field(serialization_alias="applicantUserId")
    applicant_display_name: str = Field(serialization_alias="applicantDisplayName")
    justification: str
    status: AcgApplicationStatus
    submitted_at: datetime = Field(serialization_alias="submittedAt")


class AcgApplicationPageResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    applications: list[AcgApplicationResponse]
    page: int
    page_size: int = Field(serialization_alias="pageSize")
    total: int
    total_pages: int = Field(serialization_alias="totalPages")


class DecideAcgApplicationRequest(BaseModel):
    decision: Literal["approve", "reject"]
    reason: str | None = Field(default=None, min_length=3, max_length=500)

    @field_validator("reason")
    @classmethod
    def strip_and_validate_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if len(stripped) < 3:
            raise ValueError("A reason must contain at least 3 non-whitespace characters.")
        return stripped


class AcgAdminListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    admins: list[DirectoryUserResponse]


class ActiveUserDirectoryResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    users: list[DirectoryUserResponse]
    page: int
    page_size: int = Field(serialization_alias="pageSize")
    total: int
    total_pages: int = Field(serialization_alias="totalPages")
