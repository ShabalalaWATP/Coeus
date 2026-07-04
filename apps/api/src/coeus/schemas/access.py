from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AccessControlGroupResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    acg_id: UUID = Field(serialization_alias="id")
    code: str
    name: str
    description: str
    owner_user_id: UUID | None = Field(serialization_alias="ownerUserId")
    is_active: bool = Field(serialization_alias="isActive")
    member_user_ids: list[UUID] = Field(serialization_alias="memberUserIds")


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


class ProductSummaryResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    product_id: UUID = Field(serialization_alias="id")
    title: str
    summary: str
    product_type: str = Field(serialization_alias="productType")
    status: str
    classification_level: int = Field(serialization_alias="classificationLevel")
    handling_caveats: list[str] = Field(serialization_alias="handlingCaveats")
    acg_ids: list[UUID] = Field(serialization_alias="acgIds")
    owner_team: str = Field(serialization_alias="ownerTeam")


class ProjectMemberResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: UUID = Field(serialization_alias="userId")
    role: str


class ProjectMilestoneResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    milestone_id: UUID = Field(serialization_alias="id")
    title: str
    status: str


class ProjectPlanItemResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    plan_item_id: UUID = Field(serialization_alias="id")
    title: str
    owner_role: str = Field(serialization_alias="ownerRole")
    status: str


class ProjectWorkspaceResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: UUID = Field(serialization_alias="id")
    reference: str
    name: str
    summary: str
    requester_user_id: UUID = Field(serialization_alias="requesterUserId")
    acg_ids: list[UUID] = Field(serialization_alias="acgIds")
    ticket_ids: list[UUID] = Field(serialization_alias="ticketIds")
    members: list[ProjectMemberResponse]
    milestones: list[ProjectMilestoneResponse]
    plan_items: list[ProjectPlanItemResponse] = Field(serialization_alias="planItems")
    visible_products: list[ProductSummaryResponse] = Field(serialization_alias="visibleProducts")


class ProjectWorkspaceListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    projects: list[ProjectWorkspaceResponse]


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
