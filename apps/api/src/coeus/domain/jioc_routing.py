"""Persisted inputs and outputs for the autonomous JIOC routing agent."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class JiocRoutingContext:
    context_id: UUID
    ticket_id: UUID
    schema_version: str
    requirement_revision: str
    search_outcome: str
    search_assurance: str
    search_coverage: str
    search_corpus_version: str | None
    product_offer_statuses: tuple[str, ...]
    active_work_search_completed: bool
    active_work_offer_statuses: tuple[str, ...]
    priority: str | None
    deadline: str | None
    required_output_format: str | None
    intelligence_disciplines: str | None
    area_or_region: str | None
    time_period_start: str | None
    time_period_end: str | None
    restrictions_present: bool
    created_at: datetime


@dataclass(frozen=True)
class JiocRoutingDecision:
    decision_id: UUID
    ticket_id: UUID
    context_id: UUID
    recommended_route: str
    disposition: str
    confidence: float
    rationale_codes: tuple[str, ...]
    required_clarifications: tuple[str, ...]
    policy_version: str
    created_at: datetime
