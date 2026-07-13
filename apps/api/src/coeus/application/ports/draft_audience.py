"""Port for persisted draft-product audience relationships."""

from typing import Protocol
from uuid import UUID

from coeus.domain.draft_audience import DraftAudienceReason


class DraftAudienceProjection(Protocol):
    def contains(
        self, product_id: UUID, principal_id: UUID, reason: DraftAudienceReason
    ) -> bool: ...
