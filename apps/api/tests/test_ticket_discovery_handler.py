from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.api.ticket_discovery_composition import build_ticket_discovery_handler
from coeus.core.config import Settings
from coeus.domain.enums import TicketState
from coeus.domain.jioc_routing import JiocRoutingMode
from coeus.domain.outbox import OutboxMessage
from coeus.main import create_app
from coeus.services.ticket_discovery_handler import TicketDiscoveryHandler
from rfi_search_helpers import login


@pytest.mark.asyncio
async def test_outbox_handler_retries_searching_ticket_idempotently() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user_session = await login(client, "user@example.test")
        created = await client.post(
            "/api/v1/chat/messages",
            headers={"X-CSRF-Token": str(user_session["csrfToken"])},
            json={"message": "Need a regional Baltic port activity briefing."},
        )
        ticket_id = created.json()["id"]
        edited = await client.patch(
            f"/api/v1/tickets/{ticket_id}/intake",
            headers={"X-CSRF-Token": str(user_session["csrfToken"])},
            json={
                "title": "Regional Stability Brief",
                "description": "Assess mock shipping activity and likely disruption.",
                "operationalQuestion": "What activity needs command attention?",
                "areaOrRegion": "Baltic ports",
                "timePeriodStart": "2026-06-01",
                "timePeriodEnd": "2026-07-01",
                "priority": "high",
                "supportedOperation": "Operation Harbour Sentinel",
                "urgencyJustification": "A patrol posture decision is due this week.",
                "deadline": "Friday",
                "requestingUnit": "Carrier Strike Group Atlas",
                "intelligenceDisciplines": "IMINT, OSINT",
                "requiredOutputFormat": "assessment report",
                "customerSuccessCriteria": "Identify actions for watch teams.",
            },
        )
    assert edited.status_code == 200
    actor = app.state.access_services.repository.get_user_by_username("user@example.test")
    assert actor is not None
    submitted = app.state.ticket_services.tickets.submit(actor, UUID(ticket_id))
    handler = build_ticket_discovery_handler(app, app.state.access_services.repository)
    message = _message(submitted.ticket_id)

    handler(message)
    handler(message)

    ticket = app.state.ticket_services.tickets.get_visible_ticket(actor, submitted.ticket_id)
    assert ticket.state.value == "RFI_SEARCH_INCOMPLETE"
    assert len(ticket.search_metrics) == 1


def test_outbox_handler_rejects_an_unexpected_event_type() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    handler = build_ticket_discovery_handler(app, app.state.access_services.repository)

    with pytest.raises(ValueError, match="Unexpected outbox event type"):
        handler(_message(uuid4(), event_type="unexpected"))


def test_outbox_handler_covers_fail_closed_and_rollout_paths() -> None:
    ticket_id = uuid4()
    tickets = SimpleNamespace(tickets=MagicMock())
    access = MagicMock()
    search = MagicMock()
    active_work = MagicMock()
    routing = MagicMock()

    def handler(
        *,
        automatic: bool = True,
        active: bool = True,
        agent: JiocRoutingMode | bool = JiocRoutingMode.ACTIVE,
    ):
        return TicketDiscoveryHandler(
            tickets, access, search, active_work, routing, automatic, active, agent
        )

    tickets.tickets.assignment_snapshot.return_value = ()
    handler()(_message(ticket_id))

    draft = SimpleNamespace(
        ticket_id=ticket_id,
        state=TicketState.DRAFT_INTAKE,
        requester_user_id=uuid4(),
    )
    tickets.tickets.assignment_snapshot.return_value = (draft,)
    handler()(_message(ticket_id))

    pending = SimpleNamespace(
        ticket_id=ticket_id,
        state=TicketState.JIOC_ROUTING_PENDING,
        requester_user_id=uuid4(),
    )
    tickets.tickets.assignment_snapshot.return_value = (pending,)
    handler(agent=JiocRoutingMode.DISABLED)(_message(ticket_id))
    handler(agent=JiocRoutingMode.SHADOW)(_message(ticket_id))
    handler(agent=JiocRoutingMode.ACTIVE)(_message(ticket_id))
    assert routing.route.call_args_list == [
        ((ticket_id,), {"apply": False}),
        ((ticket_id,), {"apply": True}),
    ]
    routing.defer_to_manager.assert_called_once_with(ticket_id)

    routing.reset_mock()
    routing.route.side_effect = RuntimeError("synthetic agent failure")
    handler(agent=JiocRoutingMode.ACTIVE)(_message(ticket_id))
    routing.defer_to_manager.assert_called_once_with(
        ticket_id,
        reason="routing_agent_failed",
    )
    routing.defer_to_manager.side_effect = RuntimeError("synthetic referral failure")
    with pytest.raises(RuntimeError, match="referral failure"):
        handler(agent=JiocRoutingMode.ACTIVE)(_message(ticket_id))
    routing.defer_to_manager.side_effect = None
    routing.route.side_effect = None

    searching = SimpleNamespace(
        ticket_id=ticket_id,
        state=TicketState.RFI_SEARCHING,
        requester_user_id=uuid4(),
    )
    tickets.tickets.assignment_snapshot.return_value = (searching,)
    handler(automatic=False)(_message(ticket_id))

    access.get_user.return_value = None
    with pytest.raises(LookupError, match="missing or inactive"):
        handler()(_message(ticket_id))
    access.get_user.return_value = SimpleNamespace(is_active=False)
    with pytest.raises(LookupError, match="missing or inactive"):
        handler()(_message(ticket_id))

    actor = SimpleNamespace(is_active=True)
    access.get_user.return_value = actor
    search.run.return_value = SimpleNamespace(ticket=searching)
    handler()(_message(ticket_id))

    consent = SimpleNamespace(
        ticket_id=ticket_id,
        state=TicketState.NEW_TASKING_CONSENT,
        requester_user_id=searching.requester_user_id,
        timeline=(),
    )
    search.run.return_value = SimpleNamespace(ticket=consent)
    handler(active=False)(_message(ticket_id))

    tickets.tickets.assignment_snapshot.return_value = (consent,)
    tickets.tickets.get_visible_ticket.return_value = SimpleNamespace(
        timeline=(SimpleNamespace(event_type="active_work_search_completed"),)
    )
    handler()(_message(ticket_id))
    tickets.tickets.get_visible_ticket.return_value = SimpleNamespace(timeline=())
    handler()(_message(ticket_id))
    active_work.discover.assert_called_once_with(actor, ticket_id)


def _message(ticket_id: UUID, *, event_type: str = "ticket_shadow_changed") -> OutboxMessage:
    return OutboxMessage(
        event_id=uuid4(),
        aggregate_id=ticket_id,
        aggregate_version=1,
        event_type=event_type,
        payload={"ticket_id": str(ticket_id)},
        created_at=datetime.now(UTC),
        attempt_count=1,
    )
