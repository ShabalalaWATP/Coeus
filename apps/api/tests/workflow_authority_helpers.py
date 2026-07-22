"""Test composition helpers for explicit workflow authority boundaries."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from coeus.domain.auth import AuthenticatedSession, SessionRecord, UserAccount
from coeus.persistence.codec import encode_value
from coeus.persistence.state_store import MemoryStateStore
from coeus.repositories.tickets import InMemoryTicketRepository
from coeus.services.audit import AuditLog
from coeus.services.intake import RequirementCompletenessService
from coeus.services.tickets import TicketService


def authorised_ticket_service(
    actor: UserAccount, audit: AuditLog
) -> tuple[InMemoryTicketRepository, TicketService, AuthenticatedSession]:
    state_store = MemoryStateStore()
    session = SessionRecord(
        session_id=f"test-{uuid4()}",
        user_id=actor.user_id,
        csrf_token=f"csrf-{uuid4()}",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        created_at=datetime.now(UTC),
        credential_version=actor.credential_version,
    )
    state_store.save("users", {"users": [encode_value(actor)]})
    state_store.save("sessions", {"sessions": [encode_value(session)]})
    repository = InMemoryTicketRepository(state_store)
    tickets = TicketService(
        repository,
        RequirementCompletenessService(),
        audit,
        state_store=state_store,
    )
    return repository, tickets, AuthenticatedSession(session, actor)
