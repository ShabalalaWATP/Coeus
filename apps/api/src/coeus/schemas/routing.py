from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ClarificationQuestion = Annotated[str, Field(min_length=3, max_length=300)]


class RouteApprovalRequest(BaseModel):
    route: str = Field(pattern="^(rfa|cm)$")
    override_reason: str | None = Field(
        default=None,
        min_length=3,
        max_length=1_000,
        validation_alias="overrideReason",
    )


class RouteReasonRequest(BaseModel):
    route: str = Field(pattern="^(rfa|cm)$")
    reason: str = Field(min_length=3, max_length=1_000)


class RouteClarificationRequest(BaseModel):
    route: str = Field(pattern="^(rfa|cm)$")
    reason: str = Field(min_length=3, max_length=1_000)
    questions: list[ClarificationQuestion] = Field(min_length=1, max_length=5)


class CapabilityTeamResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    team_id: str = Field(serialization_alias="teamId")
    name: str
    department: str
    keywords: list[str]
    work_packages: list[str] = Field(serialization_alias="workPackages")
    source_labels: list[str] = Field(serialization_alias="sourceLabels")


class CapabilityCatalogueResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    teams: list[CapabilityTeamResponse]


class RfaCapabilityReviewResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    review_id: UUID = Field(serialization_alias="id")
    can_satisfy: bool = Field(serialization_alias="canSatisfy")
    confidence: float
    required_clarifications: list[str] = Field(serialization_alias="requiredClarifications")
    suggested_work_packages: list[str] = Field(serialization_alias="suggestedWorkPackages")
    suggested_team_id: str | None = Field(serialization_alias="suggestedTeamId")
    suggested_team_name: str | None = Field(serialization_alias="suggestedTeamName")
    estimated_effort: str = Field(serialization_alias="estimatedEffort")
    risks: list[str]
    manager_review_required: bool = Field(serialization_alias="managerReviewRequired")
    reasoning_summary: str = Field(serialization_alias="reasoningSummary")
    created_at: datetime = Field(serialization_alias="createdAt")


class CmCapabilityReviewResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    review_id: UUID = Field(serialization_alias="id")
    can_satisfy: bool = Field(serialization_alias="canSatisfy")
    confidence: float
    required_clarifications: list[str] = Field(serialization_alias="requiredClarifications")
    suggested_collection_route: str | None = Field(serialization_alias="suggestedCollectionRoute")
    suggested_collection_team_id: str | None = Field(
        serialization_alias="suggestedCollectionTeamId"
    )
    suggested_collection_team_name: str | None = Field(
        serialization_alias="suggestedCollectionTeamName"
    )
    suggested_collection_sources: list[str] = Field(
        serialization_alias="suggestedCollectionSources"
    )
    estimated_effort: str = Field(serialization_alias="estimatedEffort")
    risks: list[str]
    manager_review_required: bool = Field(serialization_alias="managerReviewRequired")
    reasoning_summary: str = Field(serialization_alias="reasoningSummary")
    created_at: datetime = Field(serialization_alias="createdAt")


class RouteRecommendationResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    recommendation_id: UUID = Field(serialization_alias="id")
    recommended_route: str = Field(serialization_alias="recommendedRoute")
    reasoning_summary: str = Field(serialization_alias="reasoningSummary")
    created_at: datetime = Field(serialization_alias="createdAt")


class ClarificationRequestResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    clarification_id: UUID = Field(serialization_alias="id")
    route: str
    reason: str
    questions: list[str]
    requested_by_user_id: UUID = Field(serialization_alias="requestedByUserId")
    created_at: datetime = Field(serialization_alias="createdAt")


class ManagerDecisionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision_id: UUID = Field(serialization_alias="id")
    route: str
    status: str
    reason: str
    override_reason: str | None = Field(serialization_alias="overrideReason")
    actor_user_id: UUID = Field(serialization_alias="actorUserId")
    created_at: datetime = Field(serialization_alias="createdAt")


class ProjectPlanUpdateResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    update_id: UUID = Field(serialization_alias="id")
    title: str
    owner_role: str = Field(serialization_alias="ownerRole")
    status: str
    note: str
    created_at: datetime = Field(serialization_alias="createdAt")


class RoutingTicketResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticket_id: UUID = Field(serialization_alias="ticketId")
    reference: str
    requester_user_id: UUID = Field(serialization_alias="requesterUserId")
    state: str
    title: str
    priority: str | None
    rfa_review: RfaCapabilityReviewResponse | None = Field(serialization_alias="rfaReview")
    cm_review: CmCapabilityReviewResponse | None = Field(serialization_alias="cmReview")
    recommendation: RouteRecommendationResponse | None
    clarifications: list[ClarificationRequestResponse]
    agent_runs: list[str] = Field(serialization_alias="agentRuns")
    manager_decisions: list[ManagerDecisionResponse] = Field(serialization_alias="managerDecisions")
    project_plan_updates: list[ProjectPlanUpdateResponse] = Field(
        serialization_alias="projectPlanUpdates"
    )


class RoutingStatsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    route_assessment_count: int = Field(serialization_alias="routeAssessmentCount")
    rfa_review_count: int = Field(serialization_alias="rfaReviewCount")
    cm_review_count: int = Field(serialization_alias="cmReviewCount")
    clarification_count: int = Field(serialization_alias="clarificationCount")
    analyst_assignment_count: int = Field(serialization_alias="analystAssignmentCount")
    rfa_acceptance_rate: float = Field(serialization_alias="rfaAcceptanceRate")
    cm_fallback_rate: float = Field(serialization_alias="cmFallbackRate")


class RoutingQueueResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    tickets: list[RoutingTicketResponse]
    stats: RoutingStatsResponse
