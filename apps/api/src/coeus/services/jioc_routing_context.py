"""Versioned evidence assembly for autonomous JIOC routing."""

import json
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from hashlib import sha256
from typing import Protocol
from uuid import uuid4

from coeus.domain.jioc_routing import JiocRoutingContext, RoutingOperationalSnapshot
from coeus.domain.teams import OrgTeam
from coeus.domain.tickets import IntakeDetails, TicketRecord

CONTEXT_SCHEMA_VERSION = "jioc-routing-context-v2"
CAPABILITY_CATALOGUE_VERSION = "capability-catalogue-v1"
MAX_CAPACITY_AGE_SECONDS = 300


class RoutingOperationalContextPort(Protocol):
    def snapshot(
        self, ticket: TicketRecord, candidate_team_ids: tuple[str, ...]
    ) -> RoutingOperationalSnapshot: ...


class MissingOperationalContext:
    """Fail-closed default until live availability is injected by composition."""

    def snapshot(
        self, ticket: TicketRecord, candidate_team_ids: tuple[str, ...]
    ) -> RoutingOperationalSnapshot:
        del ticket, candidate_team_ids
        return RoutingOperationalSnapshot(CAPABILITY_CATALOGUE_VERSION, None, ())


class TeamDirectoryPort(Protocol):
    def list_teams(self) -> tuple[OrgTeam, ...]: ...


class AvailabilityView(Protocol):
    free: int


class TeamAvailabilityPort(Protocol):
    def availability(self, team: OrgTeam, entry_date: str) -> AvailabilityView: ...


class LiveRoutingOperationalContext:
    """Join capability IDs to active organisational teams and current free capacity."""

    def __init__(
        self,
        teams: TeamDirectoryPort,
        availability: TeamAvailabilityPort,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._teams = teams
        self._availability = availability
        self._clock = clock

    def snapshot(
        self, ticket: TicketRecord, candidate_team_ids: tuple[str, ...]
    ) -> RoutingOperationalSnapshot:
        del ticket
        captured_at = self._clock()
        day = captured_at.date().isoformat()
        teams = self._teams.list_teams()
        capacity: list[str] = []
        for capability_id in candidate_team_ids:
            matches = tuple(
                team
                for team in teams
                if team.is_active and team.capability_team_id == capability_id
            )
            if not matches:
                capacity.append(f"{capability_id}:unknown:0")
                continue
            free = sum(self._availability.availability(team, day).free for team in matches)
            status = "available" if free > 0 else "unavailable"
            capacity.append(f"{capability_id}:{status}:{free}")
        return RoutingOperationalSnapshot(
            CAPABILITY_CATALOGUE_VERSION,
            captured_at,
            tuple(capacity),
        )


def build_routing_context(
    ticket: TicketRecord,
    operational: RoutingOperationalSnapshot | None = None,
    created_at: datetime | None = None,
) -> JiocRoutingContext:
    metric = ticket.search_metrics[-1] if ticket.search_metrics else None
    intake = ticket.intake
    snapshot = operational or MissingOperationalContext().snapshot(ticket, ())
    return JiocRoutingContext(
        context_id=uuid4(),
        ticket_id=ticket.ticket_id,
        schema_version=CONTEXT_SCHEMA_VERSION,
        requirement_revision=requirement_revision(intake),
        search_outcome=metric.outcome if metric else "missing",
        search_assurance=metric.assurance if metric else "missing",
        search_coverage=metric.coverage_status if metric else "missing",
        search_corpus_version=metric.corpus_version if metric else None,
        product_offer_statuses=tuple(
            f"{offer.product_id}:{offer.status.value}" for offer in ticket.product_offers
        ),
        active_work_search_completed=any(
            item.event_type == "active_work_search_completed" for item in ticket.timeline
        ),
        active_work_offer_statuses=tuple(
            f"{offer.ticket_id}:{offer.status}" for offer in ticket.active_work_offers
        ),
        priority=intake.priority,
        deadline=intake.deadline,
        required_output_format=intake.required_output_format,
        intelligence_disciplines=intake.intelligence_disciplines,
        area_or_region=intake.area_or_region,
        time_period_start=intake.time_period_start,
        time_period_end=intake.time_period_end,
        restrictions_present=bool((intake.restrictions_or_caveats or "").strip()),
        created_at=created_at or datetime.now(UTC),
        capability_catalogue_version=snapshot.capability_catalogue_version,
        availability_snapshot_at=snapshot.captured_at,
        candidate_capacity=snapshot.candidate_capacity,
        capacity_freshness_seconds=MAX_CAPACITY_AGE_SECONDS,
    )


def requirement_revision(intake: IntakeDetails) -> str:
    """Hash keyed canonical JSON so changed or reordered fields cannot collide."""

    payload = json.dumps(
        asdict(intake),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def evidence_failures(context: JiocRoutingContext) -> tuple[str, ...]:
    """Evaluate only the persisted point-in-time context, never live ticket state."""

    failures: list[str] = []
    if context.search_assurance != "definitive" or context.search_coverage != "complete":
        failures.append("product_search_not_definitive")
    if _has_open_offer(context.product_offer_statuses):
        failures.append("product_offer_unresolved")
    if not context.active_work_search_completed:
        failures.append("active_work_search_missing")
    if _has_open_offer(context.active_work_offer_statuses):
        failures.append("active_work_offer_unresolved")
    if (
        not context.capability_catalogue_version
        or context.capability_catalogue_version == "unknown"
    ):
        failures.append("capability_catalogue_version_missing")
    if context.availability_snapshot_at is None:
        failures.append("availability_snapshot_missing")
    elif abs((context.created_at - context.availability_snapshot_at).total_seconds()) > (
        context.capacity_freshness_seconds
    ):
        failures.append("availability_snapshot_stale")
    return tuple(failures)


def _has_open_offer(statuses: tuple[str, ...]) -> bool:
    return any(value.rsplit(":", 1)[-1].casefold() == "offered" for value in statuses)


def capacity_status(context: JiocRoutingContext, team_id: str | None) -> str:
    if not team_id:
        return "unknown"
    prefix = f"{team_id}:"
    for entry in context.candidate_capacity:
        if entry.startswith(prefix):
            return entry[len(prefix) :].split(":", 1)[0]
    return "unknown"
