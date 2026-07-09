from datetime import UTC, datetime
from uuid import uuid4

from coeus.domain.tickets import WorkflowPlanUpdate
from coeus.persistence.codec import decode_value, encode_value


def test_workflow_plan_update_round_trips() -> None:
    update = WorkflowPlanUpdate(
        update_id=uuid4(),
        ticket_id=uuid4(),
        title="Confirm collection tasking",
        owner_role="Collection Manager",
        status="in_progress",
        note="Awaiting source availability confirmation.",
        created_at=datetime.now(UTC),
    )

    decoded = decode_value(encode_value(update))

    assert decoded == update
