import asyncio
from threading import Event
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app

SEED_CREDENTIAL = "CoeusLocal1!"
NEW_CREDENTIAL = "RaceProofPass2!"


async def _login(client: AsyncClient, username: str) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": SEED_CREDENTIAL},
    )
    assert response.status_code == 200
    return str(response.json()["csrfToken"])


def _settings(**overrides: object) -> Settings:
    return Settings(
        environment="test",
        persistence_provider="memory",
        seed_demo_content=False,
        argon2_memory_cost=8_192,
        auth_ip_max_attempts=100,
        **overrides,
    )


@pytest.mark.asyncio
async def test_password_change_cannot_restore_concurrent_admin_disable() -> None:
    app = create_app(_settings())
    started = Event()
    release = Event()

    async with (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as user,
        AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as admin,
    ):
        user_csrf = await _login(user, "user@example.test")
        admin_csrf = await _login(admin, "admin@example.test")
        users = await admin.get("/api/v1/admin/users")
        target = next(
            item for item in users.json()["users"] if item["username"] == "user@example.test"
        )
        hasher = app.state.auth_service._password_hasher
        original_hash = hasher.hash

        def gated_hash(credential: str) -> str:
            encoded = original_hash(credential)
            if credential == NEW_CREDENTIAL:
                started.set()
                if not release.wait(timeout=10):
                    raise TimeoutError("Administrator mutation did not complete")
            return encoded

        hasher.hash = gated_hash
        password_change = asyncio.create_task(
            user.post(
                "/api/v1/auth/password",
                headers={"X-CSRF-Token": user_csrf},
                json={
                    "currentPassword": SEED_CREDENTIAL,
                    "newPassword": NEW_CREDENTIAL,
                },
            )
        )
        assert await asyncio.to_thread(started.wait, 10)
        disabled = await admin.put(
            f"/api/v1/admin/users/{target['id']}/status",
            headers={"X-CSRF-Token": admin_csrf},
            json={"isActive": False},
        )
        release.set()
        changed = await password_change
        me = await user.get("/api/v1/auth/me")

    stored = app.state.auth_service._users.get_by_id(UUID(target["id"]))
    assert disabled.status_code == 200
    assert changed.status_code == 401
    assert me.status_code == 401
    assert stored is not None and not stored.is_active


@pytest.mark.asyncio
async def test_discarded_login_cookies_remain_within_per_user_session_limit() -> None:
    settings = _settings(session_max_per_user=5, session_max_entries=1_000)
    app = create_app(settings)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        for _index in range(12):
            client.cookies.clear()
            response = await client.post(
                "/api/v1/auth/login",
                json={"username": "user@example.test", "password": SEED_CREDENTIAL},
            )
            assert response.status_code == 200

    retained = tuple(app.state.auth_service._sessions._sessions.values())
    assert len(retained) == settings.session_max_per_user
    assert all(session.user_id == retained[0].user_id for session in retained)
