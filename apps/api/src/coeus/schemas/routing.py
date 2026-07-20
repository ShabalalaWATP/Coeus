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


class JiocInterventionRequest(BaseModel):
    action: str = Field(pattern="^(hold|resume|send_to_review)$")
    reason: str = Field(min_length=3, max_length=1_000)


class CapabilityTeamResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    team_id: str = Field(serialization_alias="teamId")
    name: str
    department: str
    keywords: list[str]
    work_packages: list[str] = Field(serialization_alias="workPackages")
    source_labels: list[str] = Field(serialization_alias="sourceLabels")
    disciplines: list[str]
    regions: list[str]
    rank: float


class CandidateTeamResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    team_id: str = Field(serialization_alias="teamId")
    name: str
    score: float
    reasons: list[str]


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
    candidate_teams: list[CandidateTeamResponse] = Field(serialization_alias="candidateTeams")


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
    candidate_teams: list[CandidateTeamResponse] = Field(serialization_alias="candidateTeams")


class RouteRecommendationResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    recommendation_id: UUID = Field(serialization_alias="id")
    recommended_route: str = Field(serialization_alias="recommendedRoute")
    reasoning_summary: str = Field(serialization_alias="reasoningSummary")
    created_at: datetime = Field(serialization_alias="createdAt")


class JiocAgentDecisionResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision_id: UUID = Field(serialization_alias="id")
    recommended_route: str = Field(serialization_alias="recommendedRoute")
    disposition: str
    confidence: float
    rationale_codes: list[str] = Field(serialization_alias="rationaleCodes")
    policy_version: str = Field(serialization_alias="policyVersion")
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


class WorkflowPlanUpdateResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    update_id: UUID = Field(serialization_alias="id")
    title: str
    owner_role: str = Field(serialization_alias="ownerRole")
    status: str
    note: str
    created_at: datetime = Field(serialization_alias="createdAt")


class PriorityAssessmentResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    score: float
    tier: str
    reasons: list[str]


class ReanalysisContextResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    product_id: UUID = Field(serialization_alias="productId")
    customer_reason: str = Field(serialization_alias="customerReason")
    unmet_criteria: list[str] = Field(serialization_alias="unmetCriteria")
    manager_rationale: str | None = Field(serialization_alias="managerRationale")


class RoutingTicketResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticket_id: UUID = Field(serialization_alias="ticketId")
    reference: str
    requester_user_id: UUID = Field(serialization_alias="requesterUserId")
    state: str
    title: str
    priority: str | None
    priority_assessment: PriorityAssessmentResponse = Field(
        serialization_alias="priorityAssessment"
    )
    rfa_review: RfaCapabilityReviewResponse | None = Field(serialization_alias="rfaReview")
    cm_review: CmCapabilityReviewResponse | None = Field(serialization_alias="cmReview")
    recommendation: RouteRecommendationResponse | None
    jioc_agent_decision: JiocAgentDecisionResponse | None = Field(
        serialization_alias="jiocAgentDecision"
    )
    clarifications: list[ClarificationRequestResponse]
    agent_runs: list[str] = Field(serialization_alias="agentRuns")
    manager_decisions: list[ManagerDecisionResponse] = Field(serialization_alias="managerDecisions")
    workflow_plan_updates: list[WorkflowPlanUpdateResponse] = Field(
        serialization_alias="workflowPlanUpdates"
    )
    reanalysis_context: ReanalysisContextResponse | None = Field(
        serialization_alias="reanalysisContext"
    )


class RoutingStatsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    jioc_queue_count: int = Field(serialization_alias="jiocQueueCount")
    collect_choice_count: int = Field(serialization_alias="collectChoiceCount")
    clarification_count: int = Field(serialization_alias="clarificationCount")
    analyst_assignment_count: int = Field(serialization_alias="analystAssignmentCount")
    rfa_acceptance_rate: float = Field(serialization_alias="rfaAcceptanceRate")
    cm_fallback_rate: float = Field(serialization_alias="cmFallbackRate")


class RoutingQueueResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    tickets: list[RoutingTicketResponse]
    stats: RoutingStatsResponse
    next_cursor: str | None = Field(serialization_alias="nextCursor")


class OversightCountResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    key: str
    count: int


class OversightTeamResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    team_id: UUID = Field(serialization_alias="teamId")
    name: str
    kind: str
    active_members: int = Field(serialization_alias="activeMembers")
    available_members: int = Field(serialization_alias="availableMembers")
    live_task_count: int = Field(serialization_alias="liveTaskCount")


class OversightAnalystResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    user_id: UUID = Field(serialization_alias="userId")
    display_name: str = Field(serialization_alias="displayName")
    team_ids: list[UUID] = Field(serialization_alias="teamIds")
    live_task_count: int = Field(serialization_alias="liveTaskCount")


class OversightTaskResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    ticket_id: UUID = Field(serialization_alias="ticketId")
    reference: str
    state: str
    route: str | None
    team_id: UUID | None = Field(serialization_alias="teamId")
    team_name: str | None = Field(serialization_alias="teamName")
    analyst_count: int = Field(serialization_alias="analystCount")
    work_package_count: int = Field(serialization_alias="workPackageCount")
    completed_work_package_count: int = Field(serialization_alias="completedWorkPackageCount")
    agent_disposition: str | None = Field(serialization_alias="agentDisposition")
    agent_confidence: float | None = Field(serialization_alias="agentConfidence")


class RoutingOversightResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    counts_by_state: list[OversightCountResponse] = Field(serialization_alias="countsByState")
    counts_by_route: list[OversightCountResponse] = Field(serialization_alias="countsByRoute")
    teams: list[OversightTeamResponse]
    analysts: list[OversightAnalystResponse]
    tasks: list[OversightTaskResponse]
