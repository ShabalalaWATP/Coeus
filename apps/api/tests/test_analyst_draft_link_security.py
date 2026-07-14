from dataclasses import replace
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.core.permissions import Permission
from coeus.domain.auth import RoleName
from coeus.main import create_app
from store_api_helpers import login, product_payload
from test_analyst_linked_product_reauthorisation import _collection_assigned_ticket


@pytest.mark.asyncio
async def test_creator_visible_draft_cannot_authorise_task_participants() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    users = app.state.auth_service._users
    analyst = users.get_by_username("analyst@example.test")
    assert analyst is not None
    elevated = replace(
        analyst,
        roles=analyst.roles | {RoleName.RFA_MANAGER},
        permissions=analyst.permissions
        | {Permission.PRODUCT_CREATE_EXISTING, Permission.RFA_ADD_PRODUCT},
    )
    users.save(elevated)
    access = app.state.access_services.repository
    acg_id = next(iter(access.active_acg_ids_for_user(elevated.user_id)))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _collection_assigned_ticket(client, app)
        session = await login(client, elevated.username)
        created = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={
                **product_payload(str(acg_id)),
                "title": "Mock Creator Visible Draft",
                "status": "draft",
            },
        )
        product_id = created.json()["id"]
        visible_before = await client.get(f"/api/v1/store/products/{product_id}")
        denied = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/products",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={"productId": product_id},
        )
        visible_after = await client.get(f"/api/v1/store/products/{product_id}")

    ticket = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
    assert created.status_code == 201
    assert visible_before.status_code == 200
    assert denied.status_code == 404
    assert denied.json()["error"]["code"] == "product_not_found"
    assert visible_after.status_code == 200
    assert ticket is not None
    assert all(str(link.product_id) != product_id for link in ticket.linked_products)
