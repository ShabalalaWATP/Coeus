from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FeedbackSubmissionRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = Field(min_length=3, max_length=1_000)
    follow_up_requested: bool = Field(default=False, validation_alias="followUpRequested")


class FeedbackSubmissionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    submission_id: UUID = Field(serialization_alias="id")
    request_id: UUID = Field(serialization_alias="requestId")
    rating: int
    comment: str
    follow_up_requested: bool = Field(serialization_alias="followUpRequested")
    created_at: datetime = Field(serialization_alias="createdAt")


class FeedbackRequestResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_id: UUID = Field(serialization_alias="id")
    ticket_id: UUID = Field(serialization_alias="ticketId")
    ticket_reference: str = Field(serialization_alias="ticketReference")
    product_id: UUID = Field(serialization_alias="productId")
    product_title: str = Field(serialization_alias="productTitle")
    status: str
    created_at: datetime = Field(serialization_alias="createdAt")
    submission: FeedbackSubmissionResponse | None


class FeedbackRequestListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    requests: list[FeedbackRequestResponse]


class AnalyticsMetricsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_tickets: int = Field(serialization_alias="totalTickets")
    active_tickets: int = Field(serialization_alias="activeTickets")
    disseminations: int
    feedback_requested: int = Field(serialization_alias="feedbackRequested")
    feedback_submitted: int = Field(serialization_alias="feedbackSubmitted")
    average_rating: float | None = Field(serialization_alias="averageRating")
    average_search_candidates: float | None = Field(serialization_alias="averageSearchCandidates")
    rfa_routes: int = Field(serialization_alias="rfaRoutes")
    collection_routes: int = Field(serialization_alias="collectionRoutes")


class ProductReuseResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    product_id: UUID = Field(serialization_alias="productId")
    reference: str
    title: str
    owner_team: str = Field(serialization_alias="ownerTeam")
    dissemination_count: int = Field(serialization_alias="disseminationCount")
    accepted_offer_count: int = Field(serialization_alias="acceptedOfferCount")
    feedback_count: int = Field(serialization_alias="feedbackCount")
    average_rating: float | None = Field(serialization_alias="averageRating")


class TrendInsightResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str
    summary: str
    signal: str
    confidence: float


class AnalyticsDashboardResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    audience: str
    metrics: AnalyticsMetricsResponse
    product_reuse: list[ProductReuseResponse] = Field(serialization_alias="productReuse")
    trends: list[TrendInsightResponse]
