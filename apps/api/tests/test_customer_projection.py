from datetime import UTC, datetime
from uuid import uuid4

from coeus.api.presenters.tickets import to_ticket_response
from coeus.core.permissions import Permission
from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.tickets import (
    AgentExecutionKind,
    AgentRun,
    AgentRunStatus,
    IntakeDetails,
    TicketRecord,
    TicketTimelineEntry,
)


def test_customer_projection_hides_internal_runs_events_and_staff_identity() -> None:
    customer = _user(frozenset())
    staff = _user(frozenset({Permission.TICKET_READ_ALL}))
    staff_id = staff.user_id
    ticket_id = uuid4()
    ticket = TicketRecord(
        ticket_id=ticket_id,
        reference="RFI-SAFE-PROJECTION",
        requester_user_id=customer.user_id,
        state=TicketState.JIOC_REVIEW,
        intake=IntakeDetails(title="Safe projection"),
        agent_runs=(
            AgentRun(
                run_id=uuid4(),
                ticket_id=ticket_id,
                agent_name="internal-agent",
                status=AgentRunStatus.COMPLETED,
                summary="Internal reasoning that a customer must not receive.",
                safety_flags=("internal_flag",),
                created_at=datetime.now(UTC),
                execution_kind=AgentExecutionKind.PROVIDER_BACKED,
                provider="synthetic-provider",
                model="synthetic-model",
                prompt_version="intake-v2",
                input_hash="sha256:" + "a" * 64,
            ),
        ),
        timeline=(
            _event(ticket_id, staff_id, "manager_override", "Sensitive override reason."),
            _event(ticket_id, staff_id, "manager_approved", "Named manager approved."),
        ),
    )

    customer_view = to_ticket_response(ticket, customer)
    staff_view = to_ticket_response(ticket, staff)

    assert customer_view.agent_runs == []
    assert [item.event_type for item in customer_view.timeline] == ["manager_approved"]
    assert customer_view.timeline[0].body == "Team review completed."
    assert customer_view.timeline[0].actor_user_id == customer.user_id
    assert staff_view.agent_runs[0].summary.startswith("Internal reasoning")
    assert staff_view.agent_runs[0].execution_kind == "provider_backed"
    assert staff_view.agent_runs[0].provider == "synthetic-provider"
    assert staff_view.agent_runs[0].prompt_version == "intake-v2"
    assert staff_view.agent_runs[0].input_hash == "sha256:" + "a" * 64
    assert staff_view.timeline[0].body == "Sensitive override reason."


def _user(permissions: frozenset[Permission]) -> UserAccount:
    return UserAccount(
        uuid4(),
        "synthetic@example.test",
        "Synthetic User",
        frozenset({RoleName.USER}),
        permissions,
        "unused",
        True,
        3,
    )


def _event(ticket_id, actor_id, event_type: str, body: str) -> TicketTimelineEntry:
    return TicketTimelineEntry(uuid4(), ticket_id, event_type, body, actor_id, datetime.now(UTC))
