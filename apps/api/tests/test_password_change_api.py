import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app

SEED_CREDENTIAL = "CoeusLocal1!"
NEW_CREDENTIAL = "FreshLocalPass2!"


def _app():
    return create_app(Settings(environment="test", argon2_memory_cost=8_192))


def _client(app) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def _login(client: AsyncClient, username: str, password: str = SEED_CREDENTIAL) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return str(response.json()["csrfToken"])


@pytest.mark.asyncio
async def test_password_change_rotates_session_and_new_password_works() -> None:
    app = _app()
    async with _client(app) as client:
        csrf = await _login(client, "user@example.test")
        changed = await client.post(
            "/api/v1/auth/password",
            headers={"X-CSRF-Token": csrf},
            json={"currentPassword": SEED_CREDENTIAL, "newPassword": NEW_CREDENTIAL},
        )
        me_after = await client.get("/api/v1/auth/me")
        old_login = await client.post(
            "/api/v1/auth/login",
            json={"username": "user@example.test", "password": SEED_CREDENTIAL},
        )
        new_login = await client.post(
            "/api/v1/auth/login",
            json={"username": "user@example.test", "password": NEW_CREDENTIAL},
        )

    assert changed.status_code == 200
    assert changed.json()["csrfToken"] != csrf
    assert changed.json()["user"]["passwordResetRequired"] is False
    assert "set-cookie" in changed.headers
    assert me_after.status_code == 200
    assert old_login.status_code == 401
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_password_change_invalidates_other_sessions() -> None:
    app = _app()
    async with _client(app) as first, _client(app) as second:
        await _login(second, "user@example.test")
        csrf = await _login(first, "user@example.test")
        changed = await first.post(
            "/api/v1/auth/password",
            headers={"X-CSRF-Token": csrf},
            json={"currentPassword": SEED_CREDENTIAL, "newPassword": NEW_CREDENTIAL},
        )
        other_session = await second.get("/api/v1/auth/me")

    assert changed.status_code == 200
    assert other_session.status_code == 401


@pytest.mark.asyncio
async def test_password_change_rejects_bad_current_weak_new_and_missing_csrf() -> None:
    app = _app()
    async with _client(app) as client:
        csrf = await _login(client, "user@example.test")
        wrong_current = await client.post(
            "/api/v1/auth/password",
            headers={"X-CSRF-Token": csrf},
            json={"currentPassword": "not-the-password", "newPassword": NEW_CREDENTIAL},
        )
        weak_new = await client.post(
            "/api/v1/auth/password",
            headers={"X-CSRF-Token": csrf},
            json={"currentPassword": SEED_CREDENTIAL, "newPassword": "short"},
        )
        missing_csrf = await client.post(
            "/api/v1/auth/password",
            json={"currentPassword": SEED_CREDENTIAL, "newPassword": NEW_CREDENTIAL},
        )
        still_valid = await client.get("/api/v1/auth/me")

    assert wrong_current.status_code == 403
    assert wrong_current.json()["error"]["code"] == "invalid_current_password"
    assert weak_new.status_code == 422
    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["error"]["code"] == "csrf_failed"
    assert still_valid.status_code == 200


@pytest.mark.asyncio
async def test_admin_credential_reset_forces_password_rotation() -> None:
    app = _app()
    async with _client(app) as admin, _client(app) as user:
        admin_csrf = await _login(admin, "admin@example.test")
        users = await admin.get("/api/v1/admin/users")
        target = next(
            item for item in users.json()["users"] if item["username"] == "user@example.test"
        )
        reset = await admin.post(
            f"/api/v1/admin/users/{target['id']}/credential-reset",
            headers={"X-CSRF-Token": admin_csrf},
        )
        temporary = str(reset.json()["temporaryCredential"])

        login = await user.post(
            "/api/v1/auth/login",
            json={"username": "user@example.test", "password": temporary},
        )
        user_csrf = str(login.json()["csrfToken"])
        blocked = await user.get("/api/v1/tickets")
        me_allowed = await user.get("/api/v1/auth/me")
        changed = await user.post(
            "/api/v1/auth/password",
            headers={"X-CSRF-Token": user_csrf},
            json={"currentPassword": temporary, "newPassword": NEW_CREDENTIAL},
        )
        unblocked = await user.get("/api/v1/tickets")

    assert reset.status_code == 200
    assert login.status_code == 200
    assert login.json()["user"]["passwordResetRequired"] is True
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "password_change_required"
    assert me_allowed.status_code == 200
    assert me_allowed.json()["user"]["passwordResetRequired"] is True
    assert changed.status_code == 200
    assert changed.json()["user"]["passwordResetRequired"] is False
    assert unblocked.status_code == 200


@pytest.mark.asyncio
async def test_forced_rotation_still_allows_logout() -> None:
    app = _app()
    async with _client(app) as admin, _client(app) as user:
        admin_csrf = await _login(admin, "admin@example.test")
        users = await admin.get("/api/v1/admin/users")
        target = next(
            item for item in users.json()["users"] if item["username"] == "user@example.test"
        )
        reset = await admin.post(
            f"/api/v1/admin/users/{target['id']}/credential-reset",
            headers={"X-CSRF-Token": admin_csrf},
        )
        login = await user.post(
            "/api/v1/auth/login",
            json={
                "username": "user@example.test",
                "password": str(reset.json()["temporaryCredential"]),
            },
        )
        logout = await user.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": str(login.json()["csrfToken"])},
        )

    assert logout.status_code == 204
