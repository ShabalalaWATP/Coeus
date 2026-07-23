"""Composition helper for the RFI search workflow."""

from coeus.services.embeddings import EmbeddingService
from coeus.services.grounded_search import GroundedSearchService
from coeus.services.rfi_search import RfiSearchService
from coeus.services.rfi_search_types import RfiAccess
from coeus.services.search_planner_agent import SearchPlannerAgent
from coeus.services.store import StoreServices
from coeus.services.tickets import TicketServices


def build_rfi_search_service(
    ticket_services: TicketServices,
    store_services: StoreServices,
    access_repository: RfiAccess,
    embeddings: EmbeddingService,
    grounded: GroundedSearchService,
    planner: SearchPlannerAgent,
) -> RfiSearchService:
    return RfiSearchService(
        ticket_services.tickets,
        store_services.search,
        store_services.details,
        access_repository,
        embeddings,
        grounded,
        planner,
        ticket_services.mutations,
    )
