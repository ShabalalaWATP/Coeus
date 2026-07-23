from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from coeus.core.config import Settings
from coeus.domain.enums import TicketState
from coeus.domain.tickets import ProductDissemination, ProductOfferStatus
from coeus.main import create_app
from coeus.services.ticket_records import timeline
from rfi_search_helpers import login, submitted_ticket


def _app() -> FastAPI:
    return create_app(
        Settings(
            environment="test",
            argon2_memory_cost=8_192,
            automatic_request_discovery_enabled=False,
        )
    )


async def _mixed_visibility_ticket(app: FastAPI, client: AsyncClient) -> tuple[str, UUID, UUID]:
    owner = await login(client, "user@example.test")
    csrf = str(owner["csrfToken"])
    ticket_id = await submitted_ticket(client, csrf)
    tagged = await client.post(
        f"/api/v1/tickets/{ticket_id}/collaborators",
        headers={"X-CSRF-Token": csrf},
        json={"username": "rfa.manager@example.test", "access": "viewer"},
    )
    run = await client.post(
        f"/api/v1/rfi-search/{ticket_id}/run",
        headers={"X-CSRF-Token": csrf},
    )
    assert tagged.status_code == 200 and run.status_code == 200

    stored = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
    assert stored is not None and stored.product_offers and stored.search_metrics
    visible_offer = stored.product_offers[0]
    hidden_product = next(
        product
        for product in app.state.store_services.repository.list_products()
        if product.metadata.title == "Collection Sensor Summary"
    )
    hidden_offer = replace(
        visible_offer,
        product_id=hidden_product.product_id,
        title=hidden_product.metadata.title,
        status=ProductOfferStatus.ACCEPTED,
    )
    accepted_metric = replace(
        stored.search_metrics[-1], accepted_product_id=hidden_product.product_id
    )
    dissemination = ProductDissemination(
        dissemination_id=uuid4(),
        ticket_id=stored.ticket_id,
        product_id=hidden_product.product_id,
        recipient_user_id=stored.requester_user_id,
        created_at=datetime.now(UTC),
    )
    app.state.ticket_services.tickets.save_system_update(
        replace(
            stored,
            state=TicketState.CLOSED_EXISTING_PRODUCT_ACCEPTED,
            product_offers=(visible_offer, hidden_offer),
            search_metrics=(*stored.search_metrics[:-1], accepted_metric),
            disseminations=(dissemination,),
            timeline=(
                *stored.timeline,
                timeline(
                    stored.ticket_id,
                    stored.requester_user_id,
                    "product_offer_accepted",
                    f"Accepted existing product {hidden_offer.title}.",
                ),
            ),
        )
    )
    return ticket_id, visible_offer.product_id, hidden_product.product_id


@pytest.mark.asyncio
async def test_mixed_visibility_derives_every_signal_from_visible_offers() -> None:
    app = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id, visible_id, hidden_id = await _mixed_visibility_ticket(app, client)

        await login(client, "rfa.manager@example.test")
        result = await client.get(f"/api/v1/rfi-search/{ticket_id}/results")
        detail = await client.get(f"/api/v1/tickets/{ticket_id}")
        listed = await client.get("/api/v1/tickets")

        owner = await login(client, "user@example.test")
        owner_result = await client.get(f"/api/v1/rfi-search/{ticket_id}/results")
        owner_detail = await client.get(f"/api/v1/tickets/{ticket_id}")

        await login(client, "admin@example.test")
        admin_result = await client.get(f"/api/v1/rfi-search/{ticket_id}/results")

    body = result.json()
    assert body["ticketState"] == "RFI_MATCH_OFFERED"
    assert body["outcome"] == "offers"
    assert body["metrics"]["acceptedProductId"] is None
    assert body["metrics"]["offeredCount"] == 1
    assert [offer["productId"] for offer in body["offers"]] == [str(visible_id)]
    assert str(hidden_id) not in result.text

    detail_body = detail.json()
    assert detail_body["state"] == "RFI_MATCH_OFFERED"
    assert detail_body["customerStatus"]["code"] == "products_offered"
    assert detail_body["releasedProductIds"] == []
    assert "product_offer_accepted" not in {item["eventType"] for item in detail_body["timeline"]}
    summary = next(item for item in listed.json()["tickets"] if item["id"] == ticket_id)
    assert summary["state"] == "RFI_MATCH_OFFERED"
    assert summary["releasedProductId"] is None

    for positive in (owner_result, admin_result):
        assert positive.json()["ticketState"] == "CLOSED_EXISTING_PRODUCT_ACCEPTED"
        assert positive.json()["metrics"]["acceptedProductId"] == str(hidden_id)
        assert {offer["productId"] for offer in positive.json()["offers"]} == {
            str(visible_id),
            str(hidden_id),
        }
    assert owner["user"]["username"] == "user@example.test"
    assert owner_detail.json()["releasedProductIds"] == [str(hidden_id)]


@pytest.mark.asyncio
async def test_ticket_list_batches_offer_visibility_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        ticket_id, _visible_id, _hidden_id = await _mixed_visibility_ticket(app, client)
        stored = app.state.ticket_services.tickets._repository.get(UUID(ticket_id))
        assert stored is not None
        many_offers = (
            *stored.product_offers,
            *(replace(stored.product_offers[0], product_id=uuid4()) for _ in range(200)),
        )
        app.state.ticket_services.tickets.save_system_update(
            replace(stored, product_offers=many_offers)
        )

        details = app.state.store_services.details
        original_batch = details.visible_product_ids
        batches: list[frozenset[UUID]] = []

        def counted_batch(actor, product_ids):  # type: ignore[no-untyped-def]
            batches.append(product_ids)
            return original_batch(actor, product_ids)

        monkeypatch.setattr(details, "visible_product_ids", counted_batch)
        monkeypatch.setattr(
            details,
            "get_visible_product",
            lambda *_args: pytest.fail("ticket list must not perform per-offer lookups"),
        )
        await login(client, "rfa.manager@example.test")
        response = await client.get("/api/v1/tickets", params={"pageSize": 100})

    assert response.status_code == 200
    assert len(batches) == 1
    assert len(batches[0]) == 202


@pytest.mark.asyncio
async def test_owned_offer_visibility_does_not_contaminate_collaborator_ticket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = _app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        first_owner = await login(client, "user@example.test")
        first_csrf = str(first_owner["csrfToken"])
        owned_ticket_id = await submitted_ticket(client, first_csrf)
        owned_run = await client.post(
            f"/api/v1/rfi-search/{owned_ticket_id}/run",
            headers={"X-CSRF-Token": first_csrf},
        )

        second_owner = await login(client, "colleague@example.test")
        second_csrf = str(second_owner["csrfToken"])
        shared_ticket_id = await submitted_ticket(client, second_csrf)
        shared_run = await client.post(
            f"/api/v1/rfi-search/{shared_ticket_id}/run",
            headers={"X-CSRF-Token": second_csrf},
        )
        tagged = await client.post(
            f"/api/v1/tickets/{shared_ticket_id}/collaborators",
            headers={"X-CSRF-Token": second_csrf},
            json={"username": "user@example.test", "access": "viewer"},
        )
        assert owned_run.status_code == 200
        assert shared_run.status_code == 200
        assert tagged.status_code == 200

        repository = app.state.ticket_services.tickets._repository
        owned = repository.get(UUID(owned_ticket_id))
        shared = repository.get(UUID(shared_ticket_id))
        actor = app.state.access_services.repository.get_user_by_username("user@example.test")
        hidden_product = next(
            product
            for product in app.state.store_services.repository.list_products()
            if product.metadata.title == "Collection Sensor Summary"
        )
        assert owned is not None and owned.product_offers and owned.search_metrics
        assert shared is not None and shared.product_offers and shared.search_metrics
        assert actor is not None

        hidden_id = hidden_product.product_id

        def hidden_accepted(ticket):  # type: ignore[no-untyped-def]
            offer = replace(
                ticket.product_offers[0],
                product_id=hidden_id,
                title=hidden_product.metadata.title,
                status=ProductOfferStatus.ACCEPTED,
            )
            metric = replace(ticket.search_metrics[-1], accepted_product_id=hidden_id)
            return replace(
                ticket,
                state=TicketState.CLOSED_EXISTING_PRODUCT_ACCEPTED,
                product_offers=(offer,),
                search_metrics=(*ticket.search_metrics[:-1], metric),
            )

        ticket_service = app.state.ticket_services.tickets
        ticket_service.save_system_update(hidden_accepted(owned))
        ticket_service.save_system_update(hidden_accepted(shared))

        details = app.state.store_services.details
        original_batch = details.visible_product_ids
        batches: list[frozenset[UUID]] = []

        def counted_batch(batch_actor, product_ids):  # type: ignore[no-untyped-def]
            batches.append(product_ids)
            return original_batch(batch_actor, product_ids)

        monkeypatch.setattr(details, "visible_product_ids", counted_batch)
        await login(client, "user@example.test")
        listed = await client.get("/api/v1/tickets", params={"pageSize": 100})
        assert len(batches) == 1
        assert batches[0] == frozenset({hidden_id})
        monkeypatch.setattr(details, "visible_product_ids", original_batch)
        owned_detail = await client.get(f"/api/v1/tickets/{owned_ticket_id}")
        shared_detail = await client.get(f"/api/v1/tickets/{shared_ticket_id}")

        await login(client, "colleague@example.test")
        shared_owner_detail = await client.get(f"/api/v1/tickets/{shared_ticket_id}")

    summaries = {item["id"]: item for item in listed.json()["tickets"]}
    assert listed.status_code == 200
    assert summaries[owned_ticket_id]["state"] == "CLOSED_EXISTING_PRODUCT_ACCEPTED"
    assert summaries[shared_ticket_id]["state"] == "RFI_SEARCH_INCOMPLETE"
    assert owned_detail.json()["state"] == "CLOSED_EXISTING_PRODUCT_ACCEPTED"
    assert owned_detail.json()["releasedProductIds"] == []
    assert shared_detail.json()["state"] == "RFI_SEARCH_INCOMPLETE"
    assert str(hidden_id) not in shared_detail.text
    assert shared_owner_detail.json()["state"] == "CLOSED_EXISTING_PRODUCT_ACCEPTED"
