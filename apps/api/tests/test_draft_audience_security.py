"""Regression coverage for object-aware Store draft audiences."""

from dataclasses import replace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.domain.auth import RoleName, UserAccount
from coeus.domain.rbac import permissions_for_roles
from coeus.main import create_app
from store_api_helpers import login, product_payload


@pytest.mark.asyncio
async def test_unrelated_same_acg_and_multi_role_users_cannot_read_draft() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    access = app.state.access_services.repository
    alpha = next(acg for acg in access.list_acgs() if "ALPHA" in acg.code)
    payload = {
        **product_payload(str(alpha.acg_id)),
        "title": "Mock Object-Aware Draft",
        "status": "draft",
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        creator_session = await login(client, "rfa.manager@example.test")
        created = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(creator_session["csrfToken"])},
            json=payload,
        )
        product = created.json()
        creator_search = await client.get(
            "/api/v1/store/products", params={"query": "Object-Aware Draft"}
        )
        creator_detail = await client.get(f"/api/v1/store/products/{product['id']}")

        _add_user_role(app, "rfa.team@example.test", RoleName.USER)
        await login(client, "rfa.team@example.test")
        unrelated_search = await client.get(
            "/api/v1/store/products", params={"query": "Object-Aware Draft"}
        )
        unrelated_detail = await client.get(f"/api/v1/store/products/{product['id']}")
        asset_id = product["assets"][0]["id"]
        unrelated_grant = await client.get(
            f"/api/v1/store/products/{product['id']}/assets/{asset_id}/access"
        )

        _add_user_role(app, "rfa.manager@example.test", RoleName.USER)
        await login(client, "rfa.manager@example.test")
        creator_grant = await client.get(
            f"/api/v1/store/products/{product['id']}/assets/{asset_id}/access"
        )

    assert created.status_code == 201
    assert product["status"] == "draft"
    assert product["id"] in {item["id"] for item in creator_search.json()["products"]}
    assert creator_detail.status_code == 200
    assert unrelated_search.status_code == 200
    assert product["id"] not in {item["id"] for item in unrelated_search.json()["products"]}
    assert unrelated_detail.status_code == 404
    assert unrelated_detail.json()["error"]["code"] == "product_not_found"
    assert unrelated_grant.status_code == 404
    assert unrelated_grant.json()["error"]["code"] == "product_not_found"
    assert creator_grant.status_code == 200
    assert creator_grant.json()["downloadToken"].startswith("asset-token-")


def _add_user_role(app: FastAPI, username: str, role: RoleName) -> None:
    auth_service = app.state.auth_service
    repository = auth_service._users
    user = repository.get_by_username(username)
    assert isinstance(user, UserAccount)
    roles = frozenset((*user.roles, role))
    repository.save(replace(user, roles=roles, permissions=permissions_for_roles(roles)))
