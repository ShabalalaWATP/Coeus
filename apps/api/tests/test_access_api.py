from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app

SEED_CREDENTIAL = "CoeusLocal1!"


async def login(client: AsyncClient, username: str) -> dict[str, object]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": SEED_CREDENTIAL},
    )
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_admin_lists_acgs_and_customer_is_denied() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as user:
        await login(user, "user@example.test")
        user_response = await user.get("/api/v1/acgs")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as admin:
        await login(admin, "admin@example.test")
        admin_response = await admin.get("/api/v1/acgs")

    assert user_response.status_code == 403
    assert admin_response.status_code == 200
    admin_codes = {acg["code"] for acg in admin_response.json()["acgs"]}
    assert {
        "ACG-ALPHA-REGIONAL",
        "ACG-BRAVO-COLLECTION",
        "ACG-CHARLIE-ASSESSMENT",
        "ACG-EU-CYBER",
        "ACG-EU-HUMINT",
        "ACG-AF-CYBER",
        "ACG-MAR-GEOINT",
    } <= admin_codes
    assert len(admin_codes) >= 43


@pytest.mark.asyncio
async def test_project_workspace_routes_are_removed() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "user@example.test")
        response = await client.get("/api/v1/projects")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_manager_can_view_relevant_acgs_but_not_unrelated_detail() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        await login(client, "rfa.manager@example.test")
        response = await client.get("/api/v1/acgs")
        collection_acg = next(
            acg for acg in app.state.access_services.repository.list_acgs() if "BRAVO" in acg.code
        )
        unrelated_response = await client.get(f"/api/v1/acgs/{collection_acg.acg_id}")

    assert response.status_code == 200
    manager_codes = {acg["code"] for acg in response.json()["acgs"]}
    assert {
        "ACG-ALPHA-REGIONAL",
        "ACG-CHARLIE-ASSESSMENT",
        "ACG-EU-CYBER",
        "ACG-EU-HUMINT",
        "ACG-ME-HUMINT",
    } <= manager_codes
    assert "ACG-BRAVO-COLLECTION" not in manager_codes
    assert unrelated_response.status_code == 404


@pytest.mark.asyncio
async def test_admin_can_create_acg_add_member_and_audit_change() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    customer = app.state.access_services.repository.get_user_by_username("user@example.test")
    assert customer is not None

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "admin@example.test")
        created = await client.post(
            "/api/v1/acgs",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={
                "code": "ACG-HOTEL-TEST",
                "name": "Hotel Test",
                "description": "Synthetic test access group.",
            },
        )
        add_member = await client.post(
            f"/api/v1/acgs/{created.json()['id']}/members",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={"userId": str(customer.user_id)},
        )
        updated = await client.patch(
            f"/api/v1/acgs/{created.json()['id']}",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={"name": "Hotel Test Updated", "isActive": False},
        )
        removed = await client.delete(
            f"/api/v1/acgs/{created.json()['id']}/members/{customer.user_id}",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
        )
        audit_response = await client.get("/api/v1/audit")

    assert created.status_code == 201
    assert add_member.status_code == 200
    assert updated.status_code == 200
    assert updated.json()["name"] == "Hotel Test Updated"
    assert updated.json()["isActive"] is False
    assert removed.status_code == 204
    assert customer.user_id in [UUID(value) for value in add_member.json()["memberUserIds"]]
    event_types = [event["eventType"] for event in audit_response.json()["events"]]
    assert "acg_created" in event_types
    assert "acg_updated" in event_types
    assert "acg_membership_added" in event_types
    assert "acg_membership_removed" in event_types


@pytest.mark.asyncio
async def test_store_manager_can_assign_acg_membership_without_global_admin() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    customer = app.state.access_services.repository.get_user_by_username("user@example.test")
    collection_acg = next(
        acg for acg in app.state.access_services.repository.list_acgs() if "BRAVO" in acg.code
    )
    assert customer is not None

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "store.manager@example.test")
        listed = await client.get("/api/v1/acgs")
        added = await client.post(
            f"/api/v1/acgs/{collection_acg.acg_id}/members",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={"userId": str(customer.user_id)},
        )
        forbidden_create = await client.post(
            "/api/v1/acgs",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={
                "code": "ACG-STORE-TEST",
                "name": "Store Test",
                "description": "Synthetic test access group.",
            },
        )

    assert listed.status_code == 200
    assert added.status_code == 200
    assert customer.user_id in [UUID(value) for value in added.json()["memberUserIds"]]
    assert forbidden_create.status_code == 403


@pytest.mark.asyncio
async def test_store_manager_cannot_self_grant_acg_membership() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    store_manager = app.state.access_services.repository.get_user_by_username(
        "store.manager@example.test"
    )
    assessment_acg = next(
        acg
        for acg in app.state.access_services.repository.list_acgs()
        if acg.code == "ACG-CHARLIE-ASSESSMENT"
    )
    assert store_manager is not None

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        session = await login(client, "store.manager@example.test")
        self_grant = await client.post(
            f"/api/v1/acgs/{assessment_acg.acg_id}/members",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={"userId": str(store_manager.user_id)},
        )

    assert self_grant.status_code == 403
    assert store_manager.user_id not in [
        membership.user_id
        for membership in app.state.access_services.repository.list_memberships_for_acg(
            assessment_acg.acg_id
        )
    ]


@pytest.mark.asyncio
async def test_access_diagnostics_explain_customer_denial() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    customer = app.state.access_services.repository.get_user_by_username("user@example.test")
    assert customer is not None
    collection_product = next(
        product
        for product in app.state.access_services.repository.list_products()
        if product.title == "Collection Sensor Summary"
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        admin_session = await login(client, "admin@example.test")
        diagnostic_response = await client.post(
            f"/api/v1/store/products/{collection_product.product_id}/access-diagnostics",
            headers={"X-CSRF-Token": str(admin_session["csrfToken"])},
            json={"userId": str(customer.user_id)},
        )

    assert diagnostic_response.status_code == 200
    payload = diagnostic_response.json()
    assert payload["allowed"] is False
    assert any(check["name"] == "acg_membership" for check in payload["checks"])


@pytest.mark.asyncio
async def test_access_diagnostics_returns_not_found_for_missing_subject() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        admin_session = await login(client, "admin@example.test")
        product_id = app.state.access_services.repository.list_products()[0].product_id
        response = await client.post(
            f"/api/v1/store/products/{product_id}/access-diagnostics",
            headers={"X-CSRF-Token": str(admin_session["csrfToken"])},
            json={"userId": "00000000-0000-0000-0000-000000000000"},
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "user_not_found"
