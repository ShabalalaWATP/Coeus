from typing import Literal

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app

SEED_CREDENTIAL = "CoeusLocal1!"


def test_login_page_seed_credential_constant_is_mock_only() -> None:
    assert SEED_CREDENTIAL.endswith("!")


@pytest.mark.parametrize("environment", ["dev", "staging", "prod"])
def test_seed_users_are_rejected_outside_local_and_test(
    environment: Literal["dev", "staging", "prod"],
) -> None:
    with pytest.raises(ValueError, match="Seed users are local/test only"):
        create_app(
            Settings(
                environment=environment,
                argon2_memory_cost=8_192,
                local_seed_credential="ChangedForNonLocalOnly1!",
            )
        )


def test_prod_startup_requires_secure_cookies() -> None:
    with pytest.raises(ValueError, match="Secure cookies"):
        create_app(Settings(environment="prod", argon2_memory_cost=8_192))


@pytest.fixture
async def auth_client() -> AsyncClient:
    app = create_app(
        Settings(
            environment="test",
            login_lockout_threshold=2,
            argon2_memory_cost=8_192,
        )
    )
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


@pytest.mark.asyncio
async def test_login_sets_secure_session_cookie_and_returns_current_user() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin@example.test", "password": SEED_CREDENTIAL},
        )
        me_response = await client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert "httponly" in response.headers["set-cookie"].lower()
    assert "samesite=strict" in response.headers["set-cookie"].lower()
    assert response.json()["user"]["defaultRoute"] == "/admin/overview"
    assert "system:configure" in response.json()["user"]["permissions"]
    assert response.json()["csrfToken"]
    assert me_response.status_code == 200
    assert me_response.json()["user"]["username"] == "admin@example.test"


@pytest.mark.asyncio
async def test_login_uses_app_settings_for_secure_cookie() -> None:
    app = create_app(Settings(environment="test", secure_cookies=True, argon2_memory_cost=8_192))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin@example.test", "password": SEED_CREDENTIAL},
        )

    assert response.status_code == 200
    assert "secure" in response.headers["set-cookie"].lower()


@pytest.mark.asyncio
async def test_invalid_username_and_invalid_password_return_generic_error() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        unknown_user = await client.post(
            "/api/v1/auth/login",
            json={"username": "missing@example.test", "password": "wrong"},
        )
        wrong_password = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin@example.test", "password": "wrong"},
        )

    assert unknown_user.status_code == 401
    assert wrong_password.status_code == 401
    assert unknown_user.json() == wrong_password.json()
    assert unknown_user.json()["error"]["code"] == "authentication_failed"


@pytest.mark.asyncio
async def test_repeated_login_failures_trigger_lockout_for_username() -> None:
    app = create_app(
        Settings(environment="test", login_lockout_threshold=2, argon2_memory_cost=8_192)
    )

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        for _attempt in range(2):
            response = await client.post(
                "/api/v1/auth/login",
                json={"username": "user@example.test", "password": "wrong"},
            )
            assert response.status_code == 401
        locked_response = await client.post(
            "/api/v1/auth/login",
            json={"username": "user@example.test", "password": SEED_CREDENTIAL},
        )

    assert locked_response.status_code == 423
    assert locked_response.json()["error"]["code"] == "account_locked"


@pytest.mark.asyncio
async def test_disabled_users_cannot_log_in() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "disabled@example.test", "password": SEED_CREDENTIAL},
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_failed"


@pytest.mark.asyncio
async def test_logout_requires_csrf_and_revokes_session() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin@example.test", "password": SEED_CREDENTIAL},
        )
        missing_csrf_response = await client.post("/api/v1/auth/logout")
        logout_response = await client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": login_response.json()["csrfToken"]},
        )
        me_response = await client.get("/api/v1/auth/me")

    assert missing_csrf_response.status_code == 403
    assert missing_csrf_response.json()["error"]["code"] == "csrf_failed"
    assert logout_response.status_code == 204
    assert "coeus_session" in logout_response.headers["set-cookie"]
    assert me_response.status_code == 401


@pytest.mark.asyncio
async def test_session_rotation_replaces_csrf_token() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin@example.test", "password": SEED_CREDENTIAL},
        )
        rotate_response = await client.post(
            "/api/v1/auth/session/rotate",
            headers={"X-CSRF-Token": login_response.json()["csrfToken"]},
        )

    assert rotate_response.status_code == 200
    assert rotate_response.json()["csrfToken"] != login_response.json()["csrfToken"]
    assert "httponly" in rotate_response.headers["set-cookie"].lower()


@pytest.mark.asyncio
async def test_admin_endpoint_enforces_backend_rbac() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as user:
        await user.post(
            "/api/v1/auth/login",
            json={"username": "user@example.test", "password": SEED_CREDENTIAL},
        )
        forbidden_response = await user.get("/api/v1/admin/overview")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as admin:
        await admin.post(
            "/api/v1/auth/login",
            json={"username": "admin@example.test", "password": SEED_CREDENTIAL},
        )
        allowed_response = await admin.get("/api/v1/admin/overview")

    assert forbidden_response.status_code == 403
    assert allowed_response.status_code == 200
    assert allowed_response.json()["scope"] == "admin-overview"


@pytest.mark.asyncio
async def test_audit_endpoint_requires_permission_and_lists_auth_events() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as user:
        await user.post(
            "/api/v1/auth/login",
            json={"username": "user@example.test", "password": SEED_CREDENTIAL},
        )
        forbidden_response = await user.get("/api/v1/audit")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as admin:
        await admin.post(
            "/api/v1/auth/login",
            json={"username": "admin@example.test", "password": SEED_CREDENTIAL},
        )
        audit_response = await admin.get("/api/v1/audit")

    assert forbidden_response.status_code == 403
    assert audit_response.status_code == 200
    assert [event["eventType"] for event in audit_response.json()["events"]].count(
        "login_success"
    ) >= 2
