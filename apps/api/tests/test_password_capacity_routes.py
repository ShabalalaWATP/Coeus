import asyncio
from threading import Event

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from coeus.core.config import Settings
from coeus.main import create_app


def _registration(username: str) -> dict[str, str]:
    return {
        "username": username,
        "displayName": "Mock Capacity Applicant",
        "justification": "Synthetic capacity regression coverage.",
        "password": "NewOperator1!x",
    }


def test_identity_services_share_one_password_work_limiter() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    hasher = app.state.auth_service._password_hasher

    assert app.state.registration_service._password_hasher is hasher
    assert app.state.user_admin_service._password_hasher is hasher


def test_password_work_capacity_configuration_is_bounded() -> None:
    assert Settings(environment="test").argon2_max_concurrent == 2
    with pytest.raises(ValidationError):
        Settings(environment="test", argon2_max_concurrent=0)
    with pytest.raises(ValidationError):
        Settings(environment="test", argon2_max_concurrent=9)


@pytest.mark.asyncio
async def test_registration_hash_blocks_known_and_unknown_login_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(
        Settings(environment="test", argon2_memory_cost=8_192, argon2_max_concurrent=1)
    )
    started = Event()
    release = Event()
    calls: list[str] = []

    class BlockingHashBackend:
        @staticmethod
        def hash(_credential: str) -> str:
            calls.append("hash")
            started.set()
            assert release.wait(timeout=5)
            return "synthetic-registration-hash"

        @staticmethod
        def verify(_stored_hash: str, _credential: str) -> bool:
            calls.append("verify")
            return False

    monkeypatch.setattr(app.state.auth_service._password_hasher, "_hasher", BlockingHashBackend())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        active = asyncio.create_task(
            client.post("/api/v1/auth/register", json=_registration("first@example.test"))
        )
        assert await asyncio.to_thread(started.wait, 5)
        unknown = await client.post(
            "/api/v1/auth/login",
            json={"username": "unknown@example.test", "password": "WrongPassword1!"},
        )
        known = await client.post(
            "/api/v1/auth/login",
            json={"username": "user@example.test", "password": "WrongPassword1!"},
        )
        release.set()
        accepted = await active

    assert accepted.status_code == 202
    assert unknown.status_code == known.status_code == 429
    assert unknown.json() == known.json()
    assert unknown.json()["error"]["code"] == "password_capacity_exhausted"
    assert calls == ["hash"]


@pytest.mark.asyncio
async def test_login_verification_blocks_registration_and_releases_its_reservation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(
        Settings(environment="test", argon2_memory_cost=8_192, argon2_max_concurrent=1)
    )
    started = Event()
    release = Event()

    class BlockingVerifyBackend:
        @staticmethod
        def verify(_stored_hash: str, _credential: str) -> bool:
            started.set()
            assert release.wait(timeout=5)
            return False

        @staticmethod
        def hash(_credential: str) -> str:
            return "synthetic-registration-hash"

    hasher = app.state.auth_service._password_hasher
    monkeypatch.setattr(hasher, "_hasher", BlockingVerifyBackend())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        active = asyncio.create_task(
            client.post(
                "/api/v1/auth/login",
                json={"username": "unknown@example.test", "password": "WrongPassword1!"},
            )
        )
        assert await asyncio.to_thread(started.wait, 5)
        denied = await client.post(
            "/api/v1/auth/register", json=_registration("retry@example.test")
        )
        release.set()
        failed_login = await active
        retried = await client.post(
            "/api/v1/auth/register", json=_registration("retry@example.test")
        )

    assert failed_login.status_code == 401
    assert denied.status_code == 429
    assert denied.json()["error"]["code"] == "password_capacity_exhausted"
    assert retried.status_code == 202
