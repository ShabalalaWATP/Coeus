from dataclasses import dataclass
from typing import Protocol

from coeus.application.ports.access import ActiveAcgReader, UserLookup
from coeus.domain.search_index import GroundedProductEvidence
from coeus.domain.search_metrics import RfiSearchMetrics
from coeus.domain.tickets import ProductOffer, TicketRecord


class RfiAccess(UserLookup, ActiveAcgReader, Protocol):
    pass


@dataclass(frozen=True)
class RfiSearchResults:
    ticket: TicketRecord
    offers: tuple[ProductOffer, ...]
    metrics: RfiSearchMetrics | None
    evidence: tuple[GroundedProductEvidence, ...] = ()
    retrieval_mode: str = "metadata_only"
    degraded_reason: str | None = None
    outcome: str = "incomplete"
    assurance: str = "assisted"
