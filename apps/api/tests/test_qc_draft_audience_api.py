from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.domain.tickets import LinkedAnalystProduct
from coeus.main import create_app
from rfi_search_helpers import login
from store_api_helpers import product_payload
from test_qc_api import _submitted_qc_ticket
from test_qc_claim_api import _add_second_qc_reviewer


@pytest.mark.asyncio
async def test_assigned_qc_draft_access_is_object_specific_and_revocable() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    access = app.state.access_services.repository
    creator = access.get_user_by_username("rfa.manager@example.test")
    first_qc = access.get_user_by_username("qc.manager@example.test")
    assert creator is not None and first_qc is not None
    acg_id = next(iter(access.active_acg_ids_for_user(creator.user_id)))
    access.add_membership(acg_id, first_qc.user_id)
    second_username = _add_second_qc_reviewer(app)
    second_qc = access.get_user_by_username(second_username)
    assert second_qc is not None
    access.add_membership(acg_id, second_qc.user_id)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        creator_session = await login(client, creator.username)
        created = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(creator_session["csrfToken"])},
            json={
                **product_payload(str(acg_id)),
                "title": "Assigned QC linked draft",
                "status": "draft",
            },
        )
        assert created.status_code == 201
        product = created.json()
        ticket_id = await _submitted_qc_ticket(client, app, "QC audience ticket draft")
        repository = app.state.ticket_services.tickets._repository
        ticket = repository.get(UUID(ticket_id))
        assert ticket is not None
        repository.save(
            replace(
                ticket,
                linked_products=(
                    *ticket.linked_products,
                    LinkedAnalystProduct(
                        link_id=uuid4(),
                        ticket_id=ticket.ticket_id,
                        product_id=UUID(product["id"]),
                        reference=product["reference"],
                        title=product["title"],
                        summary=product["summary"],
                        linked_by_user_id=creator.user_id,
                        created_at=datetime.now(UTC),
                    ),
                ),
            )
        )

        first = await login(client, first_qc.username)
        claimed = await client.post(
            f"/api/v1/qc/products/{ticket_id}/claim",
            headers={"X-CSRF-Token": str(first["csrfToken"])},
        )
        visible_search = await client.get(
            "/api/v1/store/products", params={"query": "Assigned QC linked draft"}
        )
        visible_detail = await client.get(f"/api/v1/store/products/{product['id']}")
        asset_id = product["assets"][0]["id"]
        denied_asset_grant = await client.get(
            f"/api/v1/store/products/{product['id']}/assets/{asset_id}/access"
        )

        await login(client, second_username)
        denied_search = await client.get(
            "/api/v1/store/products", params={"query": "Assigned QC linked draft"}
        )
        denied_detail = await client.get(f"/api/v1/store/products/{product['id']}")
        denied_grant = await client.get(
            f"/api/v1/store/products/{product['id']}/assets/{asset_id}/access"
        )

        first = await login(client, first_qc.username)
        released = await client.delete(
            f"/api/v1/qc/products/{ticket_id}/claim",
            headers={"X-CSRF-Token": str(first["csrfToken"])},
        )
        revoked_detail = await client.get(f"/api/v1/store/products/{product['id']}")

    assert claimed.status_code == 200
    assert product["id"] in {item["id"] for item in visible_search.json()["products"]}
    assert visible_detail.status_code == 200
    assert denied_asset_grant.status_code == 403
    assert product["id"] not in {item["id"] for item in denied_search.json()["products"]}
    assert denied_detail.status_code == 404
    assert denied_grant.status_code == 403
    assert released.status_code == 204
    assert revoked_detail.status_code == 404
