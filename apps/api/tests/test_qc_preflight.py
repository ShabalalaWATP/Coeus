from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from coeus.core.config import Settings
from coeus.domain.enums import TicketState
from coeus.domain.product_submission import DraftProductAsset, DraftProductVersion
from coeus.domain.qc import QcAgentPreflightStatus
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.main import create_app
from coeus.services.qc_preflight import QcPreflightAgent


def test_qc_agent_preflight_blocks_then_rechecks_a_revised_draft() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    actor = app.state.access_services.repository.get_user_by_username("qc.manager@example.test")
    assert actor is not None
    ticket_id = uuid4()
    draft = _draft(ticket_id, "Unmarked assessment content.")
    ticket = TicketRecord(
        ticket_id=ticket_id,
        reference="RFI-QC-PREFLIGHT",
        requester_user_id=actor.user_id,
        state=TicketState.QC_REVIEW,
        intake=IntakeDetails(operational_question="What changed?"),
        draft_products=(draft,),
    )
    repository = app.state.ticket_services.tickets._repository
    repository.save(ticket)
    agent = QcPreflightAgent(app.state.ticket_services)

    blocked_ticket, blocked = agent.ensure_current(actor, ticket)
    assert blocked.status == QcAgentPreflightStatus.BLOCKED
    assert blocked.blockers == ("synthetic_data_marker",)

    revised = replace(
        draft,
        version_id=uuid4(),
        version_number=2,
        content="MOCK DATA ONLY. Supported synthetic assessment content.",
    )
    revised_ticket = replace(
        blocked_ticket, draft_products=(*blocked_ticket.draft_products, revised)
    )
    repository.save(revised_ticket)
    passed_ticket, passed = agent.ensure_current(actor, revised_ticket)
    unchanged, repeated = agent.ensure_current(actor, passed_ticket)

    assert passed.status == QcAgentPreflightStatus.PASSED
    assert repeated == passed
    assert unchanged == passed_ticket
    assert len(passed_ticket.qc_agent_preflights) == 2
    assert passed_ticket.agent_runs[-1].agent_name == "qc-preflight-agent"


def _draft(ticket_id, content: str) -> DraftProductVersion:
    return DraftProductVersion(
        version_id=uuid4(),
        ticket_id=ticket_id,
        version_number=1,
        title="Synthetic assessment",
        summary="Synthetic assessment summary.",
        product_type="assessment",
        content=content,
        assets=(
            DraftProductAsset(uuid4(), "assessment.pdf", "pdf", "application/pdf", 64, "a" * 64),
        ),
        created_by_user_id=uuid4(),
        created_at=datetime.now(UTC),
    )
