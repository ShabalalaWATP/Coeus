from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.domain.access import AcgAccessApplication, AcgApplicationStatus
from coeus.main import create_app
from coeus.persistence.state_store import MemoryStateStore
from coeus.repositories.acg_applications import AcgApplicationRepository

SEED_CREDENTIAL = "CoeusLocal1!"


async def login(client: AsyncClient, username: str) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": SEED_CREDENTIAL},
    )
    assert response.status_code == 200
    return str(response.json()["csrfToken"])


def non_member_acg(app: object, *usernames: str):
    repository = app.state.access_services.repository
    users = [repository.get_user_by_username(username) for username in usernames]
    assert all(user is not None for user in users)
    return next(
        acg
        for acg in repository.list_acgs()
        if acg.is_active
        and all(acg.acg_id not in repository.acg_ids_for_user(user.user_id) for user in users)
    )


@pytest.mark.asyncio
async def test_every_role_can_browse_apply_withdraw_and_reapply() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    acg = non_member_acg(app, "user@example.test")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        csrf = await login(client, "user@example.test")
        catalogue = await client.get("/api/v1/acgs/catalogue?page=1&pageSize=50")
        ordinary_queue = await client.get("/api/v1/acg-applications")
        whitespace = await client.post(
            f"/api/v1/acgs/{acg.acg_id}/applications",
            headers={"X-CSRF-Token": csrf},
            json={"justification": "                 "},
        )
        submitted = await client.post(
            f"/api/v1/acgs/{acg.acg_id}/applications",
            headers={"X-CSRF-Token": csrf},
            json={"justification": "  Need synthetic access for my current task.  "},
        )
        duplicate = await client.post(
            f"/api/v1/acgs/{acg.acg_id}/applications",
            headers={"X-CSRF-Token": csrf},
            json={"justification": "A second pending request is not allowed."},
        )
        pending_catalogue = await client.get("/api/v1/acgs/catalogue?pageSize=50")
        withdrawn = await client.delete(
            f"/api/v1/acgs/{acg.acg_id}/applications/mine",
            headers={"X-CSRF-Token": csrf},
        )
        stale_withdraw = await client.delete(
            f"/api/v1/acgs/{acg.acg_id}/applications/mine",
            headers={"X-CSRF-Token": csrf},
        )
        resubmitted = await client.post(
            f"/api/v1/acgs/{acg.acg_id}/applications",
            headers={"X-CSRF-Token": csrf},
            json={"justification": "A renewed need after withdrawing the first request."},
        )

    assert catalogue.status_code == 200
    assert catalogue.json()["total"] >= len(catalogue.json()["acgs"])
    assert ordinary_queue.status_code == 200
    assert ordinary_queue.json()["applications"] == []
    assert whitespace.status_code == 422
    assert submitted.status_code == 201
    assert submitted.json()["justification"] == "Need synthetic access for my current task."
    assert duplicate.status_code == 409
    item = next(item for item in pending_catalogue.json()["acgs"] if item["id"] == str(acg.acg_id))
    assert item["applicationStatus"] == "pending"
    assert item["applicationId"] == submitted.json()["id"]
    assert withdrawn.status_code == 204
    assert stale_withdraw.status_code == 409
    assert resubmitted.status_code == 201
    assert resubmitted.json()["id"] != submitted.json()["id"]


@pytest.mark.asyncio
async def test_platform_admin_delegates_review_without_granting_membership() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    repository = app.state.access_services.repository
    acg = non_member_acg(app, "user@example.test", "colleague@example.test")
    customer = repository.get_user_by_username("user@example.test")
    colleague = repository.get_user_by_username("colleague@example.test")
    assert customer is not None and colleague is not None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as admin:
        admin_csrf = await login(admin, "admin@example.test")
        initial_roster = await admin.get(f"/api/v1/acgs/{acg.acg_id}/admins")
        delegated = await admin.put(
            f"/api/v1/acgs/{acg.acg_id}/admins/{customer.user_id}",
            headers={"X-CSRF-Token": admin_csrf},
        )
        duplicate_admin = await admin.put(
            f"/api/v1/acgs/{acg.acg_id}/admins/{customer.user_id}",
            headers={"X-CSRF-Token": admin_csrf},
        )

    assert initial_roster.status_code == 200
    assert initial_roster.json()["admins"]
    assert delegated.status_code == 200
    assert duplicate_admin.status_code == 409
    assert acg.acg_id not in repository.acg_ids_for_user(customer.user_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as user:
        customer_csrf = await login(user, "user@example.test")
        own = await user.post(
            f"/api/v1/acgs/{acg.acg_id}/applications",
            headers={"X-CSRF-Token": customer_csrf},
            json={"justification": "Need access while also administering this group."},
        )
        self_decision = await user.post(
            f"/api/v1/acg-applications/{own.json()['id']}/decision",
            headers={"X-CSRF-Token": customer_csrf},
            json={"decision": "approve"},
        )
    assert self_decision.status_code == 403

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as other:
        colleague_csrf = await login(other, "colleague@example.test")
        application = await other.post(
            f"/api/v1/acgs/{acg.acg_id}/applications",
            headers={"X-CSRF-Token": colleague_csrf},
            json={"justification": "Need access to support a synthetic assessment."},
        )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as user:
        customer_csrf = await login(user, "user@example.test")
        queue = await user.get("/api/v1/acg-applications?pageSize=1")
        approved = await user.post(
            f"/api/v1/acg-applications/{application.json()['id']}/decision",
            headers={"X-CSRF-Token": customer_csrf},
            json={"decision": "approve"},
        )
        stale = await user.post(
            f"/api/v1/acg-applications/{application.json()['id']}/decision",
            headers={"X-CSRF-Token": customer_csrf},
            json={"decision": "reject", "reason": "No longer required."},
        )

    assert queue.status_code == 200
    assert queue.json()["pageSize"] == 1
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert stale.status_code == 409
    assert acg.acg_id in repository.acg_ids_for_user(colleague.user_id)


@pytest.mark.asyncio
async def test_directory_roster_revocation_and_rejection_are_scoped() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    repository = app.state.access_services.repository
    acg = non_member_acg(app, "user@example.test", "colleague@example.test")
    customer = repository.get_user_by_username("user@example.test")
    colleague = repository.get_user_by_username("colleague@example.test")
    inactive = next(user for user in repository.list_users() if not user.is_active)
    assert customer is not None and colleague is not None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as store:
        await login(store, "store.manager@example.test")
        store_directory = await store.get("/api/v1/acgs/admin-directory?query=user&pageSize=5")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as user:
        await login(user, "user@example.test")
        forbidden_directory = await user.get("/api/v1/acgs/admin-directory")
    assert store_directory.status_code == 200
    assert forbidden_directory.status_code == 403
    assert str(inactive.user_id) not in {item["id"] for item in store_directory.json()["users"]}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as admin:
        admin_csrf = await login(admin, "admin@example.test")
        inactive_add = await admin.put(
            f"/api/v1/acgs/{acg.acg_id}/admins/{inactive.user_id}",
            headers={"X-CSRF-Token": admin_csrf},
        )
        await admin.put(
            f"/api/v1/acgs/{acg.acg_id}/admins/{customer.user_id}",
            headers={"X-CSRF-Token": admin_csrf},
        )
    assert inactive_add.status_code == 422

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as other:
        colleague_csrf = await login(other, "colleague@example.test")
        application = await other.post(
            f"/api/v1/acgs/{acg.acg_id}/applications",
            headers={"X-CSRF-Token": colleague_csrf},
            json={"justification": "Need access to support a synthetic assessment."},
        )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as user:
        customer_csrf = await login(user, "user@example.test")
        missing_reason = await user.post(
            f"/api/v1/acg-applications/{application.json()['id']}/decision",
            headers={"X-CSRF-Token": customer_csrf},
            json={"decision": "reject"},
        )
        whitespace_reason = await user.post(
            f"/api/v1/acg-applications/{application.json()['id']}/decision",
            headers={"X-CSRF-Token": customer_csrf},
            json={"decision": "reject", "reason": "   "},
        )
        rejected = await user.post(
            f"/api/v1/acg-applications/{application.json()['id']}/decision",
            headers={"X-CSRF-Token": customer_csrf},
            json={"decision": "reject", "reason": "  Need is not established.  "},
        )
    assert missing_reason.status_code == 422
    assert whitespace_reason.status_code == 422
    assert rejected.status_code == 200
    assert "reason" not in rejected.json()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as admin:
        admin_csrf = await login(admin, "admin@example.test")
        revoked = await admin.delete(
            f"/api/v1/acgs/{acg.acg_id}/admins/{customer.user_id}",
            headers={"X-CSRF-Token": admin_csrf},
        )
        stale_remove = await admin.delete(
            f"/api/v1/acgs/{acg.acg_id}/admins/{customer.user_id}",
            headers={"X-CSRF-Token": admin_csrf},
        )
        remaining_admin_id = revoked.json()["admins"][0]["id"]
        last_remove = await admin.delete(
            f"/api/v1/acgs/{acg.acg_id}/admins/{remaining_admin_id}",
            headers={"X-CSRF-Token": admin_csrf},
        )
        audit = await admin.get("/api/v1/audit")
    assert revoked.status_code == 200
    assert stale_remove.status_code == 409
    assert last_remove.status_code == 409
    events = [event for event in audit.json()["events"] if event["eventType"].startswith("acg_")]
    serialised_metadata = repr([event["metadata"] for event in events])
    assert "Need access" not in serialised_metadata
    assert "Need is not established" not in serialised_metadata

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as other:
        colleague_csrf = await login(other, "colleague@example.test")
        renewed = await other.post(
            f"/api/v1/acgs/{acg.acg_id}/applications",
            headers={"X-CSRF-Token": colleague_csrf},
            json={"justification": "A renewed synthetic need after rejection."},
        )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as user:
        customer_csrf = await login(user, "user@example.test")
        empty_after_revoke = await user.get("/api/v1/acg-applications")
        forbidden_after_revoke = await user.post(
            f"/api/v1/acg-applications/{renewed.json()['id']}/decision",
            headers={"X-CSRF-Token": customer_csrf},
            json={"decision": "approve"},
        )
    assert empty_after_revoke.json()["applications"] == []
    assert forbidden_after_revoke.status_code == 404


@pytest.mark.asyncio
async def test_acg_administrator_limit_is_enforced_incrementally() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    repository = app.state.access_services.repository
    acg = next(acg for acg in repository.list_acgs() if acg.owner_user_id is not None)
    owner_id = acg.owner_user_id
    candidates = [
        user for user in repository.list_users() if user.is_active and user.user_id != owner_id
    ]
    assert len(candidates) >= 8

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as admin:
        csrf = await login(admin, "admin@example.test")
        responses = [
            await admin.put(
                f"/api/v1/acgs/{acg.acg_id}/admins/{user.user_id}",
                headers={"X-CSRF-Token": csrf},
            )
            for user in candidates[:8]
        ]

    assert [response.status_code for response in responses[:7]] == [200] * 7
    assert responses[7].status_code == 409


def test_application_repository_preserves_history_and_latest_projection() -> None:
    state_store = MemoryStateStore()
    repository = AcgApplicationRepository(state_store)
    acg_id = uuid4()
    user_id = uuid4()
    first = AcgAccessApplication(
        application_id=uuid4(),
        acg_id=acg_id,
        applicant_user_id=user_id,
        justification="First synthetic justification.",
        status=AcgApplicationStatus.WITHDRAWN,
        submitted_at=datetime.now(UTC),
    )
    second = AcgAccessApplication(
        application_id=uuid4(),
        acg_id=acg_id,
        applicant_user_id=user_id,
        justification="Second synthetic justification.",
        status=AcgApplicationStatus.PENDING,
        submitted_at=first.submitted_at + timedelta(seconds=1),
    )
    repository.save(first)
    repository.save(second)
    repository.replace_admins(acg_id, frozenset({user_id}))
    repository.replace_admins(acg_id, frozenset())

    restarted = AcgApplicationRepository(state_store)

    assert restarted.get_by_id(first.application_id) == first
    assert restarted.get_for_user(acg_id, user_id) == second
    assert restarted.admin_user_ids(acg_id) == frozenset()
    assert restarted.is_initialised(acg_id)
