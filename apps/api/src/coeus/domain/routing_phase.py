"""Distinguish routing-phase clarification from intake-phase correction.

INFO_REQUIRED is shared between the intake loop (return to DRAFT_INTAKE)
and the JIOC routing loop (resume to JIOC_REVIEW). Routing artefacts are
the only durable discriminator: nothing writes them before consent, and
every routing path into INFO_REQUIRED leaves at least one behind (an
agent decision, a manager decision, a recommendation or a clarification
handoff).
"""

from coeus.domain.tickets import TicketRecord


def routing_history_present(ticket: TicketRecord) -> bool:
    return bool(
        ticket.route_recommendations
        or ticket.jioc_routing_decisions
        or ticket.manager_decisions
        or ticket.clarification_requests
    )
