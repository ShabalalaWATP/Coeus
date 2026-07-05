from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from coeus.domain.enums import TicketState


class MessageAuthor(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class AgentRunStatus(StrEnum):
    COMPLETED = "completed"
    QUEUED = "queued"


class ProductOfferStatus(StrEnum):
    OFFERED = "offered"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(frozen=True)
class IntakeDetails:
    title: str | None = None
    description: str | None = None
    operational_question: str | None = None
    area_or_region: str | None = None
    time_period_start: str | None = None
    time_period_end: str | None = None
    priority: str | None = None
    deadline: str | None = None
    required_output_format: str | None = None
    known_context: str | None = None
    restrictions_or_caveats: str | None = None
    customer_success_criteria: str | None = None
    suggested_project_name: str | None = None
    suggested_acg_context: str | None = None
    missing_information: tuple[str, ...] = ()
    confidence: float = 0.0


@dataclass(frozen=True)
class ChatMessage:
    message_id: UUID
    ticket_id: UUID
    author: MessageAuthor
    body: str
    created_at: datetime


@dataclass(frozen=True)
class AttachmentMetadata:
    attachment_id: UUID
    ticket_id: UUID
    name: str
    description: str
    source_type: str
    created_at: datetime


@dataclass(frozen=True)
class AgentRun:
    run_id: UUID
    ticket_id: UUID
    agent_name: str
    status: AgentRunStatus
    summary: str
    safety_flags: tuple[str, ...]
    created_at: datetime


@dataclass(frozen=True)
class TicketTimelineEntry:
    entry_id: UUID
    ticket_id: UUID
    event_type: str
    body: str
    actor_user_id: UUID
    created_at: datetime


@dataclass(frozen=True)
class ProductOffer:
    product_id: UUID
    title: str
    summary: str
    product_type: str
    match_score: float
    match_reasons: tuple[str, ...]
    classification_level: int
    releasability: tuple[str, ...]
    region: str
    time_period_start: str | None
    time_period_end: str | None
    asset_types: tuple[str, ...]
    offerable_to_user: bool
    status: ProductOfferStatus
    rejection_reason: str | None = None


@dataclass(frozen=True)
class ProductDissemination:
    dissemination_id: UUID
    ticket_id: UUID
    product_id: UUID
    recipient_user_id: UUID
    created_at: datetime


@dataclass(frozen=True)
class RfiSearchMetrics:
    run_id: UUID
    query: str
    candidate_count: int
    offered_count: int
    rejected_count: int
    accepted_product_id: UUID | None
    created_at: datetime


@dataclass(frozen=True)
class TicketRecord:
    ticket_id: UUID
    reference: str
    requester_user_id: UUID
    state: TicketState
    intake: IntakeDetails
    messages: tuple[ChatMessage, ...] = field(default_factory=tuple)
    attachments: tuple[AttachmentMetadata, ...] = field(default_factory=tuple)
    agent_runs: tuple[AgentRun, ...] = field(default_factory=tuple)
    timeline: tuple[TicketTimelineEntry, ...] = field(default_factory=tuple)
    suggested_project_name: str | None = None
    visible_product_matches: tuple[str, ...] = field(default_factory=tuple)
    product_offers: tuple[ProductOffer, ...] = field(default_factory=tuple)
    disseminations: tuple[ProductDissemination, ...] = field(default_factory=tuple)
    search_metrics: tuple[RfiSearchMetrics, ...] = field(default_factory=tuple)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
