from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChatMessageRequest(BaseModel):
    ticket_id: UUID | None = Field(default=None, validation_alias="ticketId")
    message: str = Field(min_length=3, max_length=4_000)


class IntakeUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=180)
    description: str | None = Field(default=None, min_length=3, max_length=2_000)
    operational_question: str | None = Field(
        default=None, min_length=3, max_length=500, validation_alias="operationalQuestion"
    )
    area_or_region: str | None = Field(
        default=None, min_length=2, max_length=180, validation_alias="areaOrRegion"
    )
    time_period_start: str | None = Field(
        default=None, max_length=80, validation_alias="timePeriodStart"
    )
    time_period_end: str | None = Field(
        default=None, max_length=80, validation_alias="timePeriodEnd"
    )
    priority: str | None = Field(default=None, min_length=2, max_length=40)
    deadline: str | None = Field(default=None, max_length=80)
    required_output_format: str | None = Field(
        default=None, min_length=2, max_length=120, validation_alias="requiredOutputFormat"
    )
    known_context: str | None = Field(
        default=None, max_length=2_000, validation_alias="knownContext"
    )
    restrictions_or_caveats: str | None = Field(
        default=None, max_length=1_000, validation_alias="restrictionsOrCaveats"
    )
    customer_success_criteria: str | None = Field(
        default=None, min_length=3, max_length=1_000, validation_alias="customerSuccessCriteria"
    )
    suggested_acg_context: str | None = Field(
        default=None, max_length=500, validation_alias="suggestedAcgContext"
    )
    requesting_unit: str | None = Field(
        default=None, min_length=2, max_length=180, validation_alias="requestingUnit"
    )
    intelligence_disciplines: str | None = Field(
        default=None, min_length=2, max_length=240, validation_alias="intelligenceDisciplines"
    )
    supported_operation: str | None = Field(
        default=None, min_length=2, max_length=180, validation_alias="supportedOperation"
    )
    urgency_justification: str | None = Field(
        default=None, min_length=3, max_length=500, validation_alias="urgencyJustification"
    )


class AttachmentMetadataRequest(BaseModel):
    name: str = Field(min_length=3, max_length=180)
    description: str = Field(min_length=3, max_length=500)
    source_type: str = Field(min_length=3, max_length=80, validation_alias="sourceType")


class AddInformationRequest(BaseModel):
    body: str = Field(min_length=3, max_length=2_000)


class CollaboratorAddRequest(BaseModel):
    username: str = Field(min_length=3, max_length=254)
    access: str = Field(pattern="^(editor|viewer)$")


class CollaboratorResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: UUID = Field(serialization_alias="userId")
    username: str
    display_name: str = Field(serialization_alias="displayName")
    access: str
    added_by_user_id: UUID = Field(serialization_alias="addedByUserId")
    created_at: datetime = Field(serialization_alias="createdAt")


class DirectoryUserResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: UUID = Field(serialization_alias="id")
    username: str
    display_name: str = Field(serialization_alias="displayName")


class DirectoryResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    users: list[DirectoryUserResponse]


class IntakeDetailsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str | None
    description: str | None
    operational_question: str | None = Field(serialization_alias="operationalQuestion")
    area_or_region: str | None = Field(serialization_alias="areaOrRegion")
    time_period_start: str | None = Field(serialization_alias="timePeriodStart")
    time_period_end: str | None = Field(serialization_alias="timePeriodEnd")
    priority: str | None
    deadline: str | None
    required_output_format: str | None = Field(serialization_alias="requiredOutputFormat")
    known_context: str | None = Field(serialization_alias="knownContext")
    restrictions_or_caveats: str | None = Field(serialization_alias="restrictionsOrCaveats")
    customer_success_criteria: str | None = Field(serialization_alias="customerSuccessCriteria")
    suggested_acg_context: str | None = Field(serialization_alias="suggestedAcgContext")
    requesting_unit: str | None = Field(serialization_alias="requestingUnit")
    intelligence_disciplines: str | None = Field(serialization_alias="intelligenceDisciplines")
    supported_operation: str | None = Field(serialization_alias="supportedOperation")
    urgency_justification: str | None = Field(serialization_alias="urgencyJustification")
    missing_information: list[str] = Field(serialization_alias="missingInformation")
    confidence: float


class IntakeChecklistItemResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    label: str
    value: str | None
    satisfied: bool


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    message_id: UUID = Field(serialization_alias="id")
    author: str
    body: str
    created_at: datetime = Field(serialization_alias="createdAt")


class AttachmentMetadataResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    attachment_id: UUID = Field(serialization_alias="id")
    name: str
    description: str
    source_type: str = Field(serialization_alias="sourceType")
    created_at: datetime = Field(serialization_alias="createdAt")


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: UUID = Field(serialization_alias="id")
    agent_name: str = Field(serialization_alias="agentName")
    status: str
    summary: str
    safety_flags: list[str] = Field(serialization_alias="safetyFlags")
    created_at: datetime = Field(serialization_alias="createdAt")


class TimelineEntryResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    entry_id: UUID = Field(serialization_alias="id")
    event_type: str = Field(serialization_alias="eventType")
    body: str
    actor_user_id: UUID = Field(serialization_alias="actorUserId")
    created_at: datetime = Field(serialization_alias="createdAt")


class ClarificationResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    clarification_id: UUID = Field(serialization_alias="id")
    route: str
    reason: str
    questions: list[str]
    created_at: datetime = Field(serialization_alias="createdAt")


class TicketCancelRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


class NoMatchConsentRequest(BaseModel):
    task_as_new_request: bool = Field(validation_alias="taskAsNewRequest")


class CollectChoiceRequest(BaseModel):
    # True: collect followed by RFA analysis; False: raw collect only.
    analysed: bool


class CustomerEstimateResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    earliest: datetime | None
    likely: datetime | None
    latest: datetime | None
    confidence: str
    status: str
    as_of: datetime = Field(serialization_alias="asOf")
    policy_version: str = Field(serialization_alias="policyVersion")


class CustomerJourneyStageResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    label: str
    status: str


class CustomerStatusResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    label: str
    explanation: str
    current_leg: str = Field(serialization_alias="currentLeg")
    action_required: bool = Field(serialization_alias="actionRequired")
    action_type: str | None = Field(serialization_alias="actionType")
    next_milestone: str | None = Field(serialization_alias="nextMilestone")
    canonical_ticket_id: UUID | None = Field(serialization_alias="canonicalTicketId")
    estimate: CustomerEstimateResponse | None
    journey: list[CustomerJourneyStageResponse]


class TicketResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticket_id: UUID = Field(serialization_alias="id")
    reference: str
    requester_user_id: UUID = Field(serialization_alias="requesterUserId")
    state: str
    customer_status: CustomerStatusResponse = Field(serialization_alias="customerStatus")
    intake: IntakeDetailsResponse
    intake_checklist: list[IntakeChecklistItemResponse] = Field(
        serialization_alias="intakeChecklist"
    )
    conversation_status: str = Field(serialization_alias="conversationStatus")
    collect_disposition: str | None = Field(serialization_alias="collectDisposition")
    is_ready_for_submission: bool = Field(serialization_alias="isReadyForSubmission")
    visible_product_matches: list[str] = Field(serialization_alias="visibleProductMatches")
    released_product_ids: list[UUID] = Field(serialization_alias="releasedProductIds")
    collaborators: list[CollaboratorResponse]
    messages: list[ChatMessageResponse]
    attachments: list[AttachmentMetadataResponse]
    agent_runs: list[AgentRunResponse] = Field(serialization_alias="agentRuns")
    clarification_requests: list[ClarificationResponse] = Field(
        serialization_alias="clarificationRequests"
    )
    timeline: list[TimelineEntryResponse]
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class TicketSummaryResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticket_id: UUID = Field(serialization_alias="id")
    reference: str
    requester_user_id: UUID = Field(serialization_alias="requesterUserId")
    state: str
    customer_status: CustomerStatusResponse = Field(serialization_alias="customerStatus")
    title: str | None
    priority: str | None
    is_ready_for_submission: bool = Field(serialization_alias="isReadyForSubmission")
    collaborator_count: int = Field(serialization_alias="collaboratorCount")
    released_product_id: UUID | None = Field(serialization_alias="releasedProductId")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")


class TicketListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    tickets: list[TicketSummaryResponse]
    next_cursor: UUID | None = Field(serialization_alias="nextCursor")
