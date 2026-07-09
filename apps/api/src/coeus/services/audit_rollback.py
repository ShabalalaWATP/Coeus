from coeus.domain.auth import UserAccount
from coeus.domain.tickets import TicketRecord
from coeus.services.audit import AuditLog
from coeus.services.tickets import TicketService


def record_ticket_audit_or_rollback(
    tickets: TicketService,
    audit_log: AuditLog,
    original_ticket: TicketRecord,
    event_type: str,
    actor: UserAccount,
    details: dict[str, str],
) -> None:
    try:
        audit_log.record(event_type, str(actor.user_id), details)
    except Exception:
        tickets.save_system_update(original_ticket)
        raise
