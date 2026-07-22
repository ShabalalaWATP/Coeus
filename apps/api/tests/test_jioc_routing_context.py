from dataclasses import fields, replace
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from coeus.domain.enums import TicketState
from coeus.domain.jioc_routing import RoutingOperationalSnapshot
from coeus.domain.teams import OrgTeam, TeamKind
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.services.jioc_routing_context import (
    LiveRoutingOperationalContext,
    build_routing_context,
    capacity_status,
    evidence_failures,
)


def test_live_operational_context_joins_capability_ids_and_aggregates_capacity() -> None:
    capability_id = "rfa-maritime"
    active = OrgTeam(
        uuid4(),
        "Maritime One",
        TeamKind.RFA,
        capability_team_id=capability_id,
    )
    second = replace(active, team_id=uuid4(), name="Maritime Two")
    inactive = replace(active, team_id=uuid4(), name="Inactive", is_active=False)
    teams = SimpleNamespace(list_teams=lambda: (active, second, inactive))
    availability = SimpleNamespace(
        availability=lambda team, _day: SimpleNamespace(free=1 if team.is_active else 99)
    )
    now = datetime(2026, 7, 20, 12, tzinfo=UTC)
    provider = LiveRoutingOperationalContext(teams, availability, lambda: now)

    snapshot = provider.snapshot(_ticket(), (capability_id, "missing"))

    assert snapshot.captured_at == now
    assert snapshot.candidate_capacity == (
        f"{capability_id}:available:2",
        "missing:unknown:0",
    )


def test_context_rejects_missing_catalogue_version_and_unknown_team() -> None:
    ticket = _ticket()
    now = datetime.now(UTC)
    context = build_routing_context(ticket, RoutingOperationalSnapshot("", now, ()), now)

    assert "capability_catalogue_version_missing" in evidence_failures(context)
    assert capacity_status(context, None) == "unknown"
    assert capacity_status(context, "missing-team") == "unknown"


def test_requirement_revision_is_keyed_and_covers_every_intake_field() -> None:
    ticket = _ticket()
    baseline = IntakeDetails()
    revisions: set[str] = set()
    for field in fields(IntakeDetails):
        if field.name == "missing_information":
            changed: object = ("synthetic_field",)
        elif field.name == "confidence":
            changed = 0.5
        else:
            changed = "synthetic value"
        context = build_routing_context(
            replace(ticket, intake=replace(baseline, **{field.name: changed}))
        )
        revisions.add(context.requirement_revision)

    assert len(revisions) == len(fields(IntakeDetails))
    urgent = build_routing_context(
        replace(ticket, intake=replace(baseline, urgency_justification="Synthetic urgency."))
    )
    ordinary = build_routing_context(replace(ticket, intake=baseline))
    assert urgent.requirement_revision != ordinary.requirement_revision


def _ticket() -> TicketRecord:
    return TicketRecord(
        ticket_id=uuid4(),
        reference="RFI-ROUTING-CONTEXT",
        requester_user_id=uuid4(),
        state=TicketState.JIOC_ROUTING_PENDING,
        intake=IntakeDetails(),
    )
