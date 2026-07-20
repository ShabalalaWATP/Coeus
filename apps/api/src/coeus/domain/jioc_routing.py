"""Persisted inputs and outputs for the autonomous JIOC routing agent."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

ROUTING_POLICY_VERSION = "jioc-routing-policy-v2"
ROUTING_EVALUATION_VERSION = "jioc-routing-eval-v2"
ROUTING_RELEASE = f"{ROUTING_POLICY_VERSION}:{ROUTING_EVALUATION_VERSION}"


class JiocRoutingMode(StrEnum):
    """Rollout authority for the deterministic routing agent."""

    DISABLED = "disabled"
    SHADOW = "shadow"
    ACTIVE = "active"


def normalise_routing_mode(value: JiocRoutingMode | bool) -> JiocRoutingMode:
    """Accept the former boolean control while deployments migrate to modes."""

    if isinstance(value, bool):
        return JiocRoutingMode.ACTIVE if value else JiocRoutingMode.DISABLED
    return value


@dataclass(frozen=True)
class RoutingOperationalSnapshot:
    """Versioned, point-in-time operational evidence supplied to routing."""

    capability_catalogue_version: str
    captured_at: datetime | None
    # Entries are ``<capability-team-id>:available|unavailable|unknown:<free>``.
    candidate_capacity: tuple[str, ...]


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
    capability_catalogue_version: str = "unknown"
    availability_snapshot_at: datetime | None = None
    candidate_capacity: tuple[str, ...] = ()
    capacity_freshness_seconds: int = 300


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
    evidence_outcome: str = "legacy"
