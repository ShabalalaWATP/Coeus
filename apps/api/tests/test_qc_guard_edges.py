from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.domain.enums import TicketState
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.main import create_app
from coeus.services.quality_control import QualityControlService
from rfi_search_helpers import login


def test_qc_state_and_transition_guards_fail_closed() -> None:
    ticket = TicketRecord(
        ticket_id=uuid4(),
        reference="TCK-QC-GUARD",
        requester_user_id=uuid4(),
        state=TicketState.CANCELLED,
        intake=IntakeDetails(),
    )

    with pytest.raises(AppError, match="not awaiting QC"):
        QualityControlService._ensure_state(ticket, TicketState.QC_REVIEW)
    with pytest.raises(AppError, match="cannot move"):
        QualityControlService._ensure_transition(
            TicketState.CANCELLED, TicketState.DISSEMINATION_READY
        )


@pytest.mark.asyncio
async def test_qc_detail_hides_ticket_outside_review_lifecycle(tmp_path: Path) -> None:
    app = create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            local_object_storage_path=str(tmp_path / "objects"),
        )
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        user = await login(client, "user@example.test")
        created = await client.post(
            "/api/v1/chat/messages",
            headers={"X-CSRF-Token": str(user["csrfToken"])},
            json={"message": "Need a synthetic QC guard briefing."},
        )
        await login(client, "qc.manager@example.test")
        hidden = await client.get(f"/api/v1/qc/products/{created.json()['id']}")

    assert hidden.status_code == 404
    assert hidden.json()["error"]["code"] == "product_not_found"
