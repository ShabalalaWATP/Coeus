from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RejectProductOfferRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=1_000)


class RfiProductOfferResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    product_id: UUID = Field(serialization_alias="productId")
    title: str
    summary: str
    product_type: str = Field(serialization_alias="productType")
    match_score: float = Field(serialization_alias="matchScore")
    match_reasons: list[str] = Field(serialization_alias="matchReasons")
    classification_level: int = Field(serialization_alias="classificationLevel")
    releasability: list[str]
    region: str
    time_period_start: str | None = Field(serialization_alias="timePeriodStart")
    time_period_end: str | None = Field(serialization_alias="timePeriodEnd")
    asset_types: list[str] = Field(serialization_alias="assetTypes")
    offerable_to_user: bool = Field(serialization_alias="offerableToUser")
    status: str
    rejection_reason: str | None = Field(serialization_alias="rejectionReason")


class RfiSearchMetricsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: UUID = Field(serialization_alias="runId")
    query: str
    candidate_count: int = Field(serialization_alias="candidateCount")
    offered_count: int = Field(serialization_alias="offeredCount")
    rejected_count: int = Field(serialization_alias="rejectedCount")
    accepted_product_id: UUID | None = Field(serialization_alias="acceptedProductId")
    created_at: datetime = Field(serialization_alias="createdAt")


class RfiSearchResultsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticket_id: UUID = Field(serialization_alias="ticketId")
    ticket_state: str = Field(serialization_alias="ticketState")
    offers: list[RfiProductOfferResponse]
    metrics: RfiSearchMetricsResponse | None
