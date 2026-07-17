from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SimilarRequestDuplicateRequest(BaseModel):
    withdraw_source: bool = Field(default=False, validation_alias="withdrawSource")


class SimilarRequestResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticket_id: UUID = Field(serialization_alias="ticketId")
    reference: str
    title: str
    state: str
    score: float
    reasons: list[str]
    already_linked: bool = Field(serialization_alias="alreadyLinked")
    already_marked_duplicate: bool = Field(serialization_alias="alreadyMarkedDuplicate")
    request_kind: str = Field(serialization_alias="requestKind")
    approved_route: str | None = Field(serialization_alias="approvedRoute")
    assigned_team: str | None = Field(serialization_alias="assignedTeam")
    requesting_unit: str | None = Field(serialization_alias="requestingUnit")
    supported_operation: str | None = Field(serialization_alias="supportedOperation")
    time_period_start: str | None = Field(serialization_alias="timePeriodStart")
    time_period_end: str | None = Field(serialization_alias="timePeriodEnd")


class SimilarRequestNoticeResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    matches: list[SimilarRequestResponse]


class SimilarRequestListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    matches: list[SimilarRequestResponse]


class SimilarRequestJoinResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    joined_ticket_id: UUID = Field(serialization_alias="joinedTicketId")
    reference: str
