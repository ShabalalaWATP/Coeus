from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SimilarRequestResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticket_id: UUID = Field(serialization_alias="ticketId")
    reference: str
    title: str
    state: str
    score: float
    reasons: list[str]
    already_linked: bool = Field(serialization_alias="alreadyLinked")


class SimilarRequestNoticeResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    matches: list[SimilarRequestResponse]
    hidden_matches_present: bool = Field(serialization_alias="hiddenMatchesPresent")


class SimilarRequestListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    matches: list[SimilarRequestResponse]


class SimilarRequestJoinResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    joined_ticket_id: UUID = Field(serialization_alias="joinedTicketId")
    reference: str
