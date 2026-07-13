"""Effective assigned-reviewer state for Quality Control work."""

from uuid import UUID

from coeus.domain.enums import TicketState
from coeus.domain.qc import QcClaimStatus
from coeus.domain.tickets import TicketRecord

ACTIVE_QC_ASSIGNMENT_STATES = frozenset(
    {
        TicketState.QC_REVIEW,
        TicketState.REWORK_REQUIRED,
    }
)


def active_qc_reviewer_id(ticket: TicketRecord) -> UUID | None:
    """Return the reviewer only while the workflow relationship is active."""
    if ticket.state not in ACTIVE_QC_ASSIGNMENT_STATES:
        return None
    return ticket.qc_reviewer_user_id


def qc_claim_status(ticket: TicketRecord, actor_user_id: UUID) -> QcClaimStatus:
    reviewer_id = active_qc_reviewer_id(ticket)
    if reviewer_id is None:
        return QcClaimStatus.AVAILABLE
    if reviewer_id == actor_user_id:
        return QcClaimStatus.CLAIMED_BY_YOU
    return QcClaimStatus.CLAIMED
