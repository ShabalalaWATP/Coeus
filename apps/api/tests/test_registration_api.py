import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.main import create_app

SEED_CREDENTIAL = "CoeusLocal1!"
NEW_CREDENTIAL = "NewOperator1!x"

SUBMIT_PAYLOAD = {
    "username": "new.operator@example.test",
    "displayName": "New Operator",
    "justification": "Mock regional reporting duties.",
    "password": NEW_CREDENTIAL,
}


def _client(settings: Settings | None = None) -> AsyncClient:
    app = create_app(
        settings
        or Settings(
            environment="test",
            argon2_memory_cost=8_192,
        )
    )
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def _login(client: AsyncClient, username: str, password: str = SEED_CREDENTIAL) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return str(response.json()["csrfToken"])


@pytest.mark.asyncio
async def test_registration_submission_is_generic_and_admin_can_approve() -> None:
    async with _client() as client:
        submitted = await client.post("/api/v1/auth/register", json=SUBMIT_PAYLOAD)
        assert submitted.status_code == 202
        assert submitted.json() == {"status": "pending"}

        csrf = await _login(client, "admin@example.test")
        pending = await client.get("/api/v1/admin/registrations")
        assert pending.status_code == 200
        registrations = pending.json()["registrations"]
        assert len(registrations) == 1
        assert registrations[0]["username"] == "new.operator@example.test"
        assert registrations[0]["status"] == "pending"
        assert "password" not in registrations[0]
        assert "passwordHash" not in registrations[0]

        approved = await client.post(
            f"/api/v1/admin/registrations/{registrations[0]['id']}/approve",
            headers={"X-CSRF-Token": csrf},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"

        empty = await client.get("/api/v1/admin/registrations")
        assert empty.json()["registrations"] == []

        login = await client.post(
            "/api/v1/auth/login",
            json={"username": "new.operator@example.test", "password": NEW_CREDENTIAL},
        )
        assert login.status_code == 200
        assert login.json()["user"]["roles"] == ["User"]
        assert login.json()["user"]["defaultRoute"] == "/app/requests"


@pytest.mark.asyncio
async def test_rejected_registration_cannot_log_in() -> None:
    async with _client() as client:
        await client.post("/api/v1/auth/register", json=SUBMIT_PAYLOAD)
        csrf = await _login(client, "admin@example.test")
        pending = await client.get("/api/v1/admin/registrations")
        registration_id = pending.json()["registrations"][0]["id"]

        rejected = await client.post(
            f"/api/v1/admin/registrations/{registration_id}/reject",
            headers={"X-CSRF-Token": csrf},
            json={"reason": "Duties not confirmed."},
        )
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "rejected"

        login = await client.post(
            "/api/v1/auth/login",
            json={"username": "new.operator@example.test", "password": NEW_CREDENTIAL},
        )
        assert login.status_code == 401

        decided_again = await client.post(
            f"/api/v1/admin/registrations/{registration_id}/approve",
            headers={"X-CSRF-Token": csrf},
        )
        assert decided_again.status_code == 409
        assert decided_again.json()["error"]["code"] == "registration_decided"


@pytest.mark.asyncio
async def test_duplicate_and_existing_usernames_stay_generic() -> None:
    async with _client() as client:
        first = await client.post("/api/v1/auth/register", json=SUBMIT_PAYLOAD)
        duplicate = await client.post("/api/v1/auth/register", json=SUBMIT_PAYLOAD)
        existing = await client.post(
            "/api/v1/auth/register",
            json={**SUBMIT_PAYLOAD, "username": "admin@example.test"},
        )
        assert first.status_code == 202
        assert duplicate.status_code == 202
        assert existing.status_code == 202

        await _login(client, "admin@example.test")
        pending = await client.get("/api/v1/admin/registrations")
        assert len(pending.json()["registrations"]) == 1


@pytest.mark.asyncio
async def test_registration_submissions_are_throttled_at_capacity() -> None:
    settings = Settings(
        environment="test",
        argon2_memory_cost=8_192,
        registration_max_pending=1,
    )
    async with _client(settings) as client:
        first = await client.post("/api/v1/auth/register", json=SUBMIT_PAYLOAD)
        assert first.status_code == 202
        throttled = await client.post(
            "/api/v1/auth/register",
            json={**SUBMIT_PAYLOAD, "username": "second.operator@example.test"},
        )
        assert throttled.status_code == 429
        assert throttled.json()["error"]["code"] == "registration_throttled"


@pytest.mark.asyncio
async def test_registration_payload_validation_rejects_bad_input() -> None:
    async with _client() as client:
        bad_email = await client.post(
            "/api/v1/auth/register",
            json={**SUBMIT_PAYLOAD, "username": "not-an-email"},
        )
        short_password = await client.post(
            "/api/v1/auth/register",
            json={**SUBMIT_PAYLOAD, "password": "short"},
        )
        assert bad_email.status_code == 422
        assert short_password.status_code == 422


@pytest.mark.asyncio
async def test_registration_review_requires_permission_and_csrf() -> None:
    async with _client() as client:
        await client.post("/api/v1/auth/register", json=SUBMIT_PAYLOAD)

        await _login(client, "user@example.test")
        forbidden = await client.get("/api/v1/admin/registrations")
        assert forbidden.status_code == 403

        csrf = await _login(client, "admin@example.test")
        pending = await client.get("/api/v1/admin/registrations")
        registration_id = pending.json()["registrations"][0]["id"]

        missing_csrf = await client.post(
            f"/api/v1/admin/registrations/{registration_id}/approve",
        )
        assert missing_csrf.status_code == 403
        assert missing_csrf.json()["error"]["code"] == "csrf_failed"

        unknown = await client.post(
            "/api/v1/admin/registrations/00000000-0000-0000-0000-000000000000/approve",
            headers={"X-CSRF-Token": csrf},
        )
        assert unknown.status_code == 404


@pytest.mark.asyncio
async def test_registration_decisions_require_reviewer_permission() -> None:
    async with _client() as client:
        await client.post("/api/v1/auth/register", json=SUBMIT_PAYLOAD)
        admin_csrf = await _login(client, "admin@example.test")
        pending = await client.get("/api/v1/admin/registrations")
        registration_id = pending.json()["registrations"][0]["id"]

        user_csrf = await _login(client, "user@example.test")
        forbidden = await client.post(
            f"/api/v1/admin/registrations/{registration_id}/approve",
            headers={"X-CSRF-Token": user_csrf},
        )
        assert forbidden.status_code == 403
        assert forbidden.json()["error"]["code"] == "forbidden"

        admin_csrf = await _login(client, "admin@example.test")
        approved = await client.post(
            f"/api/v1/admin/registrations/{registration_id}/approve",
            headers={"X-CSRF-Token": admin_csrf},
        )
        assert approved.status_code == 200
