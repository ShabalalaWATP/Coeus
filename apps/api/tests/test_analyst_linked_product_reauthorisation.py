from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response

from coeus.core.config import Settings
from coeus.core.errors import AppError
from coeus.domain.auth import RoleName, UserAccount
from coeus.main import create_app
from coeus.services.analyst_workflow import (
    ANALYST_LINKED_PRODUCT_LIMIT,
    ANALYST_TASK_LIST_LIMIT,
)
from rfi_search_helpers import login, submitted_ticket
from routing_helpers import assignment_team_id
from store_api_helpers import product_payload
from test_analyst_api import _draft_payload


def _assert_product_hidden(response: Response, product_id: str) -> None:
    assert response.status_code == 200, response.text
    assert product_id not in {
        item["productId"] for item in response.json().get("linkedProducts", [])
    }


@pytest.mark.asyncio
async def test_every_task_response_reauthorises_linked_products() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    access = app.state.access_services.repository
    original_user = access.get_user_by_username("analyst@example.test")
    assert original_user is not None
    replacement = next(
        user
        for user in access.list_users()
        if RoleName.INTELLIGENCE_ANALYST in user.roles
        and user.user_id != original_user.user_id
        and user.username == "analyst.3@example.test"
    )
    original_acg_ids = access.active_acg_ids_for_user(original_user.user_id)
    replacement_acg_ids = access.active_acg_ids_for_user(replacement.user_id)
    product_acg_id = next(iter(original_acg_ids - replacement_acg_ids))

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _collection_assigned_ticket(client, app)
        product_id = await _create_published_product(
            client,
            app,
            original_user,
            "Mock Reauthorised Published Product",
            product_acg_id,
        )
        original = await login(client, "analyst@example.test")
        linked = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/products",
            headers={"X-CSRF-Token": str(original["csrfToken"])},
            json={"productId": product_id},
        )
        assert linked.status_code == 200
        assert product_id in {item["productId"] for item in linked.json()["linkedProducts"]}

        manager = await login(client, "collection.manager@example.test")
        manager_denied = await client.get(f"/api/v1/store/products/{product_id}")
        team_id = await assignment_team_id(client, "cm")
        reassigned = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/assign",
            headers={"X-CSRF-Token": str(manager["csrfToken"])},
            json={"analystUserIds": [str(replacement.user_id)], "teamId": team_id},
        )
        assert manager_denied.status_code == 404
        _assert_product_hidden(reassigned, product_id)

        replacement_session = await login(client, replacement.username)
        replacement_denied = await client.get(f"/api/v1/store/products/{product_id}")
        tasks = await client.get("/api/v1/analyst/tasks")
        detail = await client.get(f"/api/v1/analyst/tasks/{ticket_id}")
        note = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/notes",
            headers={"X-CSRF-Token": str(replacement_session["csrfToken"])},
            json={"body": "Current-policy response check."},
        )
        package_id = note.json()["workPackages"][0]["id"]
        package = await client.patch(
            f"/api/v1/analyst/tasks/{ticket_id}/work-packages/{package_id}",
            headers={"X-CSRF-Token": str(replacement_session["csrfToken"])},
            json={"status": "complete"},
        )
        draft = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/drafts",
            headers={"X-CSRF-Token": str(replacement_session["csrfToken"])},
            json=_draft_payload("Reauthorised response draft"),
        )
        for remaining in draft.json()["workPackages"]:
            if remaining["status"] != "complete":
                package = await client.patch(
                    f"/api/v1/analyst/tasks/{ticket_id}/work-packages/{remaining['id']}",
                    headers={"X-CSRF-Token": str(replacement_session["csrfToken"])},
                    json={"status": "complete"},
                )
        submitted = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/submit",
            headers={"X-CSRF-Token": str(replacement_session["csrfToken"])},
        )

    assert replacement_denied.status_code == 404
    assert tasks.status_code == 200
    assert product_id not in {
        link["productId"] for task in tasks.json()["tasks"] for link in task["linkedProducts"]
    }
    for response in (detail, note, package, draft, submitted):
        _assert_product_hidden(response, product_id)


def _can_read_product(app: FastAPI, user: UserAccount, product_id: UUID) -> bool:
    try:
        app.state.store_services.details.get_visible_product(user, product_id)
    except AppError:
        return False
    return True


async def _create_published_product(
    client: AsyncClient, app: FastAPI, actor: UserAccount, title: str, acg_id: UUID | None = None
) -> str:
    access = app.state.access_services.repository
    target_acg_id = acg_id or next(iter(access.active_acg_ids_for_user(actor.user_id)))
    session = await login(client, "admin@example.test")
    response = await client.post(
        "/api/v1/store/products",
        headers={"X-CSRF-Token": str(session["csrfToken"])},
        json={
            **product_payload(str(target_acg_id)),
            "title": title,
            "description": "Synthetic published product for visibility regression coverage.",
            "status": "published",
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


@pytest.mark.asyncio
async def test_linking_cannot_create_its_own_draft_audience_authority() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    access = app.state.access_services.repository
    analyst = access.get_user_by_username("analyst@example.test")
    creator = access.get_user_by_username("rfa.manager@example.test")
    assert analyst is not None
    assert creator is not None
    shared_acg_ids = access.active_acg_ids_for_user(analyst.user_id).intersection(
        access.active_acg_ids_for_user(creator.user_id)
    )
    shared_acg = next(acg for acg in access.list_acgs() if acg.acg_id in shared_acg_ids)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _collection_assigned_ticket(client, app)
        admin_session = await login(client, "admin@example.test")
        published = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(admin_session["csrfToken"])},
            json={
                **product_payload(str(shared_acg.acg_id)),
                "title": "Mock Readable Published Product",
                "description": "Synthetic published product visible to the assigned analyst.",
                "status": "published",
            },
        )
        readable_product_id = published.json()["id"]
        creator_session = await login(client, creator.username)
        created = await client.post(
            "/api/v1/store/products",
            headers={"X-CSRF-Token": str(creator_session["csrfToken"])},
            json={
                **product_payload(str(shared_acg.acg_id)),
                "title": "Mock Unrelated Same-ACG Draft",
                "description": "Synthetic draft hidden from the assigned analyst.",
                "status": "draft",
            },
        )
        product_id = created.json()["id"]

        analyst_session = await login(client, analyst.username)
        before = await client.get(f"/api/v1/store/products/{product_id}")
        denied = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/products",
            headers={"X-CSRF-Token": str(analyst_session["csrfToken"])},
            json={"productId": product_id},
        )
        after = await client.get(f"/api/v1/store/products/{product_id}")
        allowed = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/products",
            headers={"X-CSRF-Token": str(analyst_session["csrfToken"])},
            json={"productId": readable_product_id},
        )

    ticket = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
    assert published.status_code == 201
    assert created.status_code == 201
    assert before.status_code == 404
    assert denied.status_code == 404
    assert denied.json()["error"]["code"] == "product_not_found"
    assert after.status_code == 404
    assert ticket is not None
    assert all(str(link.product_id) != product_id for link in ticket.linked_products)
    assert allowed.status_code == 200
    assert readable_product_id in {item["productId"] for item in allowed.json()["linkedProducts"]}


@pytest.mark.asyncio
async def test_analyst_task_and_link_reauthorisation_work_is_bounded() -> None:
    app = create_app(Settings(environment="test", argon2_memory_cost=8_192))
    actor = app.state.access_services.repository.get_user_by_username("analyst@example.test")
    assert actor is not None
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id = await _collection_assigned_ticket(client, app)
        product_id = await _create_published_product(
            client, app, actor, "Mock Bounded Published Product"
        )
        session = await login(client, actor.username)
        linked = await client.post(
            f"/api/v1/analyst/tasks/{ticket_id}/products",
            headers={"X-CSRF-Token": str(session["csrfToken"])},
            json={"productId": product_id},
        )
    assert linked.status_code == 200

    repository = app.state.ticket_services.tickets._repository
    ticket = repository.get(UUID(ticket_id))
    assert ticket is not None
    link = ticket.linked_products[0]
    capped = replace(
        ticket,
        linked_products=tuple(
            replace(link, link_id=uuid4()) for _index in range(ANALYST_LINKED_PRODUCT_LIMIT)
        ),
    )
    repository.save(capped)

    visible = app.state.analyst_workflow_service.visible_linked_products(actor, capped)
    with pytest.raises(AppError) as raised:
        app.state.analyst_workflow_service.link_product(actor, capped.ticket_id, uuid4())
    for index in range(ANALYST_TASK_LIST_LIMIT):
        repository.save(
            replace(
                capped,
                ticket_id=uuid4(),
                reference=f"TCK-BOUND-{index:04d}",
            )
        )

    assert len(visible) == ANALYST_LINKED_PRODUCT_LIMIT
    assert raised.value.code == "linked_product_limit_reached"
    assert len(app.state.analyst_workflow_service.list_tasks(actor)) == ANALYST_TASK_LIST_LIMIT


async def _collection_assigned_ticket(client: AsyncClient, app: FastAPI) -> str:
    requester = await login(client, "user@example.test")
    csrf = str(requester["csrfToken"])
    ticket_id = await submitted_ticket(
        client,
        csrf,
        title="Arctic sensor collection",
        area_or_region="Arctic fisheries",
        output_format="collection plan",
    )
    search = await client.post(
        f"/api/v1/rfi-search/{ticket_id}/run", headers={"X-CSRF-Token": csrf}
    )
    assert search.status_code == 200
    if search.json()["ticketState"] == "RFI_MATCH_OFFERED":
        for offer in search.json()["offers"]:
            search = await client.post(
                f"/api/v1/rfi-search/{ticket_id}/offers/{offer['productId']}/reject",
                headers={"X-CSRF-Token": csrf},
                json={"reason": "Need a new collection plan."},
            )
    elif search.json()["ticketState"] == "RFI_NO_MATCH":
        search = await client.post(
            f"/api/v1/tickets/{ticket_id}/no-match-consent",
            headers={"X-CSRF-Token": csrf},
            json={"taskAsNewRequest": True},
        )
    state = search.json().get("ticketState", search.json().get("state"))
    assert state == "JIOC_REVIEW"

    jioc = await login(client, "jioc.team@example.test")
    jioc_csrf = str(jioc["csrfToken"])
    routed = await client.post(
        f"/api/v1/routing/{ticket_id}/run", headers={"X-CSRF-Token": jioc_csrf}
    )
    approved = await client.post(
        f"/api/v1/routing/{ticket_id}/approve",
        headers={"X-CSRF-Token": jioc_csrf},
        json={"route": "cm"},
    )
    assert routed.status_code == 200
    assert approved.json()["state"] == "COLLECT_CHOICE"
    user = await login(client, "user@example.test")
    chosen = await client.post(
        f"/api/v1/tickets/{ticket_id}/collect-choice",
        headers={"X-CSRF-Token": str(user["csrfToken"])},
        json={"analysed": False},
    )
    assert chosen.status_code == 200
    assert chosen.json()["state"] == "ANALYST_ASSIGNMENT"
    manager = await login(client, "collection.manager@example.test")
    manager_csrf = str(manager["csrfToken"])
    analyst = app.state.access_services.repository.get_user_by_username("analyst@example.test")
    assert analyst is not None
    team_id = await assignment_team_id(client, "cm")
    assigned = await client.post(
        f"/api/v1/analyst/tasks/{ticket_id}/assign",
        headers={"X-CSRF-Token": manager_csrf},
        json={"analystUserIds": [str(analyst.user_id)], "teamId": team_id},
    )
    assert assigned.status_code == 200
    return ticket_id
