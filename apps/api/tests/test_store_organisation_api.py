from unittest.mock import Mock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.main import create_app
from coeus.persistence.state_store import MemoryStateStore
from coeus.services import store_projects, store_subscriptions
from coeus.services.audit import AuditLog
from store_api_helpers import login


async def _visible_product_id(client: AsyncClient, product_type: str) -> str:
    response = await client.get("/api/v1/store/products", params={"productType": product_type})
    assert response.status_code == 200
    return str(response.json()["products"][0]["id"])


@pytest.mark.asyncio
async def test_project_collaboration_lifecycle_and_owner_controls() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://testserver") as owner,
        AsyncClient(transport=transport, base_url="http://testserver") as member,
        AsyncClient(transport=transport, base_url="http://testserver") as outsider,
    ):
        owner_session = await login(owner, "user@example.test")
        member_session = await login(member, "colleague@example.test")
        await login(outsider, "admin@example.test")
        owner_headers = {"X-CSRF-Token": str(owner_session["csrfToken"])}
        member_headers = {"X-CSRF-Token": str(member_session["csrfToken"])}

        missing_csrf = await owner.post(
            "/api/v1/store/projects", json={"name": "No token", "purpose": "Blocked"}
        )
        assert missing_csrf.status_code == 403

        created = await owner.post(
            "/api/v1/store/projects",
            headers=owner_headers,
            json={
                "name": "Eastern Europe",
                "purpose": "Track regional reporting and unanswered questions.",
                "region": "Eastern Europe",
                "dateFrom": "2026-01-01",
                "dateTo": "2026-12-31",
            },
        )
        assert created.status_code == 201
        project_id = created.json()["id"]
        assert created.json()["owner"] is True
        listed = await owner.get("/api/v1/store/projects")
        assert listed.status_code == 200
        assert listed.json()[0]["id"] == project_id
        assert (await outsider.get(f"/api/v1/store/projects/{project_id}")).status_code == 404

        member_added = await owner.post(
            f"/api/v1/store/projects/{project_id}/members",
            headers=owner_headers,
            json={"username": "colleague@example.test"},
        )
        assert member_added.status_code == 200
        assert len(member_added.json()["members"]) == 2

        member_cannot_invite = await member.post(
            f"/api/v1/store/projects/{project_id}/members",
            headers=member_headers,
            json={"username": "admin@example.test"},
        )
        assert member_cannot_invite.status_code == 403

        product_id = await _visible_product_id(owner, "assessment_report")
        added_product = await member.put(
            f"/api/v1/store/projects/{project_id}/products/{product_id}",
            headers=member_headers,
        )
        assert added_product.status_code == 200
        assert added_product.json()["products"][0]["id"] == product_id

        note = await member.post(
            f"/api/v1/store/projects/{project_id}/entries",
            headers=member_headers,
            json={"kind": "question", "body": "What has changed since the last report?"},
        )
        assert note.status_code == 200
        assert note.json()["entries"][0]["author"]["displayName"] == "Billy Gilmour"

        removed_product = await member.delete(
            f"/api/v1/store/projects/{project_id}/products/{product_id}",
            headers=member_headers,
        )
        assert removed_product.status_code == 200
        assert removed_product.json()["products"] == []

        archived = await owner.put(
            f"/api/v1/store/projects/{project_id}/status",
            headers=owner_headers,
            json={"archived": True},
        )
        assert archived.status_code == 200
        blocked_note = await member.post(
            f"/api/v1/store/projects/{project_id}/entries",
            headers=member_headers,
            json={"kind": "note", "body": "Should not persist"},
        )
        assert blocked_note.status_code == 409

        await owner.put(
            f"/api/v1/store/projects/{project_id}/status",
            headers=owner_headers,
            json={"archived": False},
        )
        member_id = next(item["id"] for item in member_added.json()["members"] if not item["owner"])
        removed = await owner.delete(
            f"/api/v1/store/projects/{project_id}/members/{member_id}",
            headers=owner_headers,
        )
        assert removed.status_code == 200
        owner_view = await owner.get(f"/api/v1/store/projects/{project_id}")
        assert owner_view.json()["entries"][0]["author"]["displayName"] == "Former member"
        assert (await member.get(f"/api/v1/store/projects/{project_id}")).status_code == 404


@pytest.mark.asyncio
async def test_project_never_exposes_products_hidden_from_a_member() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://testserver") as admin,
        AsyncClient(transport=transport, base_url="http://testserver") as customer,
    ):
        admin_session = await login(admin, "admin@example.test")
        customer_session = await login(customer, "user@example.test")
        admin_headers = {"X-CSRF-Token": str(admin_session["csrfToken"])}
        customer_headers = {"X-CSRF-Token": str(customer_session["csrfToken"])}
        created = await admin.post(
            "/api/v1/store/projects",
            headers=admin_headers,
            json={"name": "Controlled project", "purpose": "Access boundary proof"},
        )
        project_id = created.json()["id"]
        await admin.post(
            f"/api/v1/store/projects/{project_id}/members",
            headers=admin_headers,
            json={"username": "user@example.test"},
        )
        hidden_product_id = await _visible_product_id(admin, "sigint_mock")
        await admin.put(
            f"/api/v1/store/projects/{project_id}/products/{hidden_product_id}",
            headers=admin_headers,
        )

        customer_view = await customer.get(f"/api/v1/store/projects/{project_id}")
        assert customer_view.status_code == 200
        assert customer_view.json()["products"] == []
        assert customer_view.json()["visibleProductCount"] == 0
        assert all(
            item["action"] != "project_product_added" for item in customer_view.json()["activity"]
        )
        hidden_add = await customer.put(
            f"/api/v1/store/projects/{project_id}/products/{hidden_product_id}",
            headers=customer_headers,
        )
        assert hidden_add.status_code == 404


@pytest.mark.asyncio
async def test_subscription_lifecycle_is_private_and_stores_criteria_only() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    transport = ASGITransport(app=app)
    async with (
        AsyncClient(transport=transport, base_url="http://testserver") as owner,
        AsyncClient(transport=transport, base_url="http://testserver") as other,
    ):
        owner_session = await login(owner, "user@example.test")
        other_session = await login(other, "admin@example.test")
        owner_headers = {"X-CSRF-Token": str(owner_session["csrfToken"])}
        other_headers = {"X-CSRF-Token": str(other_session["csrfToken"])}
        payload = {
            "name": "Eastern Europe weekly",
            "cadence": "weekly",
            "criteria": {"query": "regional stability", "region": "Eastern Europe"},
        }
        created = await owner.post(
            "/api/v1/store/subscriptions", headers=owner_headers, json=payload
        )
        assert created.status_code == 201
        subscription_id = created.json()["id"]
        assert "products" not in created.json()
        assert created.json()["criteria"]["query"] == "regional stability"

        duplicate = await owner.post(
            "/api/v1/store/subscriptions", headers=owner_headers, json=payload
        )
        assert duplicate.status_code == 409
        empty = await owner.post(
            "/api/v1/store/subscriptions",
            headers=owner_headers,
            json={"name": "Empty", "cadence": "manual", "criteria": {}},
        )
        assert empty.status_code == 422

        paused = await owner.put(
            f"/api/v1/store/subscriptions/{subscription_id}",
            headers=owner_headers,
            json={**payload, "enabled": False},
        )
        assert paused.status_code == 200
        assert paused.json()["enabled"] is False
        assert (await owner.get("/api/v1/store/subscriptions")).json() == [paused.json()]

        second = await owner.post(
            "/api/v1/store/subscriptions",
            headers=owner_headers,
            json={
                "name": "Second subscription",
                "cadence": "manual",
                "criteria": {"tag": "regional"},
            },
        )
        rename_conflict = await owner.put(
            f"/api/v1/store/subscriptions/{second.json()['id']}",
            headers=owner_headers,
            json={**payload, "enabled": True},
        )
        assert rename_conflict.status_code == 409

        cross_user = await other.delete(
            f"/api/v1/store/subscriptions/{subscription_id}", headers=other_headers
        )
        assert cross_user.status_code == 404
        deleted = await owner.delete(
            f"/api/v1/store/subscriptions/{subscription_id}", headers=owner_headers
        )
        assert deleted.status_code == 204


def test_project_and_subscription_services_enforce_limits_and_audit_rollback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    access = Mock()
    actor = Mock()
    actor.user_id = uuid4()
    project_audit = Mock(spec=AuditLog)
    project_audit.record.side_effect = RuntimeError("audit unavailable")
    project_state = MemoryStateStore()
    projects = store_projects.StoreProjectService(project_state, project_audit, access)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        projects.create(
            actor, name="Project", purpose="Purpose", region=None, date_from=None, date_to=None
        )
    assert project_state.load(store_projects.PROJECT_NAMESPACE) == {"projects": []}

    monkeypatch.setattr(store_subscriptions, "MAX_SUBSCRIPTIONS_PER_USER", 1)
    subscriptions = store_subscriptions.StoreSubscriptionService(MemoryStateStore(), AuditLog())
    criteria = store_subscriptions.SubscriptionCriteria(query="regional")
    subscriptions.create(actor.user_id, name="First", cadence="daily", criteria=criteria)
    with pytest.raises(AppError) as limit_error:
        subscriptions.create(actor.user_id, name="Second", cadence="weekly", criteria=criteria)
    assert limit_error.value.code == "subscription_limit_reached"
    with pytest.raises(AppError) as missing_error:
        subscriptions.delete(actor.user_id, uuid4())
    assert missing_error.value.code == "subscription_not_found"
