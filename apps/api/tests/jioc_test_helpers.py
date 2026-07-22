from datetime import UTC, datetime
from uuid import UUID, uuid4

from coeus.domain.tickets import CmCapabilityReview, RfaCapabilityReview


def rfa_review(ticket_id: UUID, can_satisfy: bool, confidence: float) -> RfaCapabilityReview:
    return RfaCapabilityReview(
        uuid4(),
        ticket_id,
        can_satisfy,
        confidence,
        (),
        (),
        None,
        "bounded",
        (),
        False,
        "Synthetic RFA capability review.",
        datetime.now(UTC),
    )


def cm_review(ticket_id: UUID, can_satisfy: bool, confidence: float) -> CmCapabilityReview:
    return CmCapabilityReview(
        uuid4(),
        ticket_id,
        can_satisfy,
        confidence,
        (),
        None,
        (),
        "bounded",
        (),
        False,
        "Synthetic CM capability review.",
        datetime.now(UTC),
    )
