from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.domain.access import ProductStatus
from coeus.main import create_app
from rfi_search_helpers import login
from test_product_release_api import _ticket_awaiting_release


@pytest.mark.asyncio
async def test_release_ignores_notification_failure_audit_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _ticket_awaiting_release(client, app)

        def fail_notify(*_args: object, **_kwargs: object) -> None:
            raise RuntimeError("notification backend unavailable")

        monkeypatch.setattr(app.state.notification_service, "notify", fail_notify)
        audit_log = app.state.product_release_service._audit_log
        original_record = audit_log.record

        def fail_notification_failure_audit(
            event_type: str,
            actor_user_id: str | None = None,
            metadata: dict[str, str] | None = None,
        ) -> None:
            if event_type == "product_release_notification_failed":
                raise RuntimeError("notification failure audit unavailable")
            original_record(event_type, actor_user_id, metadata)

        monkeypatch.setattr(audit_log, "record", fail_notification_failure_audit)

        manager = await login(client, "rfa.manager@example.test")
        released = await client.post(
            f"/api/v1/routing/{ticket_id}/release",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"route": "rfa"},
        )

    ticket = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
    assert ticket is not None
    product = app.state.store_services.repository.get_product(
        ticket.product_index_records[-1].product_id
    )
    assert released.status_code == 200
    assert released.json()["state"] == "DISSEMINATION_READY"
    assert product is not None
    assert product.metadata.status == ProductStatus.PUBLISHED
