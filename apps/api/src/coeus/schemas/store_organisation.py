from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from coeus.schemas.store import StoreProductResponse


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    purpose: str = Field(min_length=1, max_length=2_000)
    region: str | None = Field(default=None, max_length=80)
    date_from: str | None = Field(
        default=None, validation_alias="dateFrom", pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    date_to: str | None = Field(
        default=None, validation_alias="dateTo", pattern=r"^\d{4}-\d{2}-\d{2}$"
    )

    @model_validator(mode="after")
    def valid_dates(self) -> "ProjectCreateRequest":
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("dateFrom must be on or before dateTo")
        return self


class ProjectMemberAddRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)


class ProjectStatusRequest(BaseModel):
    archived: bool


class ProjectEntryCreateRequest(BaseModel):
    kind: Literal["note", "question"]
    body: str = Field(min_length=1, max_length=2_000)

    @model_validator(mode="after")
    def bounded_question(self) -> "ProjectEntryCreateRequest":
        if self.kind == "question" and len(self.body) > 500:
            raise ValueError("Questions must be at most 500 characters")
        return self


class ProjectMemberResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: UUID = Field(serialization_alias="id")
    username: str
    display_name: str = Field(serialization_alias="displayName")
    owner: bool


class ProjectEntryResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    entry_id: UUID = Field(serialization_alias="id")
    kind: Literal["note", "question"]
    body: str
    author: ProjectMemberResponse
    created_at: datetime = Field(serialization_alias="createdAt")


class ProjectActivityResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    activity_id: UUID = Field(serialization_alias="id")
    action: str
    actor_display_name: str = Field(serialization_alias="actorDisplayName")
    occurred_at: datetime = Field(serialization_alias="occurredAt")


class ProjectSummaryResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: UUID = Field(serialization_alias="id")
    name: str
    purpose: str
    region: str | None
    date_from: str | None = Field(serialization_alias="dateFrom")
    date_to: str | None = Field(serialization_alias="dateTo")
    archived: bool
    owner: bool
    member_count: int = Field(serialization_alias="memberCount")
    visible_product_count: int = Field(serialization_alias="visibleProductCount")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class ProjectDetailResponse(ProjectSummaryResponse):
    members: list[ProjectMemberResponse]
    products: list[StoreProductResponse]
    entries: list[ProjectEntryResponse]
    activity: list[ProjectActivityResponse]


class SubscriptionCriteriaRequest(BaseModel):
    query: str | None = Field(default=None, max_length=200)
    product_type: str | None = Field(default=None, validation_alias="productType", max_length=80)
    region: str | None = Field(default=None, max_length=180)
    tag: str | None = Field(default=None, max_length=80)
    source_type: str | None = Field(default=None, validation_alias="sourceType", max_length=80)
    date_from: str | None = Field(
        default=None, validation_alias="dateFrom", pattern=r"^\d{4}-\d{2}-\d{2}$"
    )
    date_to: str | None = Field(
        default=None, validation_alias="dateTo", pattern=r"^\d{4}-\d{2}-\d{2}$"
    )

    @model_validator(mode="after")
    def valid_dates(self) -> "SubscriptionCriteriaRequest":
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("dateFrom must be on or before dateTo")
        return self


class SubscriptionUpsertRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    cadence: Literal["manual", "daily", "weekly"]
    enabled: bool = True
    criteria: SubscriptionCriteriaRequest


class SubscriptionCriteriaResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    query: str | None
    product_type: str | None = Field(serialization_alias="productType")
    region: str | None
    tag: str | None
    source_type: str | None = Field(serialization_alias="sourceType")
    date_from: str | None = Field(serialization_alias="dateFrom")
    date_to: str | None = Field(serialization_alias="dateTo")


class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    subscription_id: UUID = Field(serialization_alias="id")
    name: str
    cadence: Literal["manual", "daily", "weekly"]
    enabled: bool
    criteria: SubscriptionCriteriaResponse
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")
