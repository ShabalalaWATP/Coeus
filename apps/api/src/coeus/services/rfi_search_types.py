from dataclasses import dataclass

from coeus.domain.search_index import GroundedProductEvidence
from coeus.domain.search_metrics import RfiSearchMetrics
from coeus.domain.tickets import ProductOffer, TicketRecord


@dataclass(frozen=True)
class RfiSearchResults:
    ticket: TicketRecord
    offers: tuple[ProductOffer, ...]
    metrics: RfiSearchMetrics | None
    evidence: tuple[GroundedProductEvidence, ...] = ()
    retrieval_mode: str = "metadata_only"
    degraded_reason: str | None = None
