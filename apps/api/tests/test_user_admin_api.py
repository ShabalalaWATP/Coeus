import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app

SEED_CREDENTIAL = "CoeusLocal1!"


async def login(client: AsyncClient, username: str) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": SEED_CREDENTIAL},
    )
    assert response.status_code == 200
    return str(response.json()["csrfToken"])


@pytest.mark.asyncio
async def test_admin_user_management_updates_user_and_revokes_sessions() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))

    async with (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as admin,
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as user,
    ):
        user_csrf = await login(user, "user@example.test")
        assert user_csrf
        admin_csrf = await login(admin, "admin@example.test")
        users = await admin.get("/api/v1/admin/users")
        target = next(
            item for item in users.json()["users"] if item["username"] == "user@example.test"
        )

        clearance = await admin.put(
            f"/api/v1/admin/users/{target['id']}/clearance",
            headers={"X-CSRF-Token": admin_csrf},
            json={"clearanceLevel": 4},
        )
        roles = await admin.put(
            f"/api/v1/admin/users/{target['id']}/roles",
            headers={"X-CSRF-Token": admin_csrf},
            json={"roles": ["Intelligence Analyst"]},
        )
        old_session = await user.get("/api/v1/auth/me")
        disabled = await admin.put(
            f"/api/v1/admin/users/{target['id']}/status",
            headers={"X-CSRF-Token": admin_csrf},
            json={"isActive": False},
        )
        disabled_login = await user.post(
            "/api/v1/auth/login",
            json={"username": "user@example.test", "password": SEED_CREDENTIAL},
        )

    assert clearance.status_code == 200
    assert clearance.json()["clearanceLevel"] == 4
    assert roles.status_code == 200
    assert roles.json()["roles"] == ["Intelligence Analyst"]
    assert old_session.status_code == 401
    assert disabled.status_code == 200
    assert disabled.json()["isActive"] is False
    assert disabled_login.status_code == 401


@pytest.mark.asyncio
async def test_admin_can_reset_user_credential_without_leaking_secret() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))

    async with (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as admin,
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as user,
    ):
        await login(user, "user@example.test")
        admin_csrf = await login(admin, "admin@example.test")
        users = await admin.get("/api/v1/admin/users")
        target = next(
            item for item in users.json()["users"] if item["username"] == "user@example.test"
        )
        reset = await admin.post(
            f"/api/v1/admin/users/{target['id']}/credential-reset",
            headers={"X-CSRF-Token": admin_csrf},
        )
        old_session = await user.get("/api/v1/auth/me")
        old_credential = await user.post(
            "/api/v1/auth/login",
            json={"username": "user@example.test", "password": SEED_CREDENTIAL},
        )
        new_credential = await user.post(
            "/api/v1/auth/login",
            json={
                "username": "user@example.test",
                "password": reset.json()["temporaryCredential"],
            },
        )
        audit = await admin.get("/api/v1/audit")

    assert reset.status_code == 200
    assert reset.json()["temporaryCredential"].startswith("Istari-")
    assert old_session.status_code == 401
    assert old_credential.status_code == 401
    assert new_credential.status_code == 200
    reset_events = [
        event for event in audit.json()["events"] if event["eventType"] == "user_credential_reset"
    ]
    assert reset_events
    assert "temporaryCredential" not in reset_events[-1]["metadata"]
    assert reset.json()["temporaryCredential"] not in str(reset_events[-1]["metadata"])


@pytest.mark.asyncio
async def test_admin_user_management_rejects_self_and_invalid_role_changes() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        admin_csrf = await login(client, "admin@example.test")
        users = await client.get("/api/v1/admin/users")
        admin_user = next(
            item for item in users.json()["users"] if item["username"] == "admin@example.test"
        )
        target = next(
            item for item in users.json()["users"] if item["username"] == "user@example.test"
        )

        self_change = await client.put(
            f"/api/v1/admin/users/{admin_user['id']}/status",
            headers={"X-CSRF-Token": admin_csrf},
            json={"isActive": False},
        )
        invalid_role = await client.put(
            f"/api/v1/admin/users/{target['id']}/roles",
            headers={"X-CSRF-Token": admin_csrf},
            json={"roles": ["Wizard"]},
        )
        await login(client, "user@example.test")
        forbidden = await client.get("/api/v1/admin/users")

    assert self_change.status_code == 409
    assert self_change.json()["error"]["code"] == "self_modification"
    assert invalid_role.status_code == 422
    assert invalid_role.json()["error"]["code"] == "role_unknown"
    assert forbidden.status_code == 403
