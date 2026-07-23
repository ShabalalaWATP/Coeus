"""Commit-time authority evidence for QC release."""

from coeus.core.permissions import Permission
from coeus.domain.auth import AuthenticatedSession, UserAccount
from coeus.domain.store import StoreProduct
from coeus.domain.tickets import TicketRecord
from coeus.domain.workflow_authority import QcCommitAuthority, WorkflowCommitAuthority
from coeus.services.qc_ingestion import latest_draft


def release_authority(
    authenticated: AuthenticatedSession,
    ticket: TicketRecord,
    product: StoreProduct,
    recipient: UserAccount | None,
) -> WorkflowCommitAuthority:
    actor = authenticated.user
    draft = latest_draft(ticket)
    return WorkflowCommitAuthority(
        actor,
        authenticated.session,
        frozenset({Permission.QC_APPROVE}),
        qc=QcCommitAuthority(
            draft.classification_level,
            draft.acg_ids,
            product.metadata.classification_level,
            product.metadata.acg_ids,
            recipient,
        ),
    )
