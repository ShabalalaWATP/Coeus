from dataclasses import replace
from uuid import UUID

from fastapi import FastAPI

from coeus.domain.enums import TicketState
from coeus.services.active_work_discovery import ActiveWorkDiscoveryService


def prepare_active_work_review(app: FastAPI, username: str, ticket_id: str) -> None:
    actor = app.state.access_services.repository.get_user_by_username(username)
    assert actor is not None
    ticket = app.state.ticket_services.tickets.get_visible_ticket(actor, UUID(ticket_id))
    app.state.ticket_services.tickets.save_system_update(
        replace(ticket, state=TicketState.NEW_TASKING_CONSENT)
    )
    ActiveWorkDiscoveryService(
        app.state.ticket_services,
        app.state.similar_request_service,
    ).discover(actor, UUID(ticket_id))
