"""Application composition for durable automatic ticket discovery."""

from fastapi import FastAPI

from coeus.application.ports.access import UserLookup
from coeus.services.active_work_discovery import ActiveWorkDiscoveryService
from coeus.services.similar_requests import SimilarRequestService
from coeus.services.ticket_discovery_handler import TicketDiscoveryHandler
from coeus.services.tickets import TicketServices


def build_ticket_discovery_handler(app: FastAPI, access: UserLookup) -> TicketDiscoveryHandler:
    tickets: TicketServices = app.state.ticket_services
    similar: SimilarRequestService = app.state.similar_request_service
    active_work = ActiveWorkDiscoveryService(tickets, similar)
    return TicketDiscoveryHandler(
        tickets,
        access,
        app.state.rfi_search_service,
        active_work,
        app.state.jioc_routing_agent_service,
        app.state.settings.automatic_request_discovery_enabled,
        app.state.settings.active_work_offers_enabled,
        app.state.settings.jioc_agent_routing_enabled,
    )
