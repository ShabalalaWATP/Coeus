from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from coeus.core.errors import AppError
from coeus.services.analyst_workflow import (
    ANALYST_LINKED_PRODUCT_LIMIT,
    ANALYST_TASK_LIST_LIMIT,
)
from rfi_search_helpers import login
from test_analyst_linked_product_reauthorisation import (
    _collection_assigned_ticket,
    _create_published_product,
    _legacy_routing_app,
)


@pytest.mark.asyncio
async def test_analyst_task_and_link_reauthorisation_work_is_bounded() -> None:
    app = _legacy_routing_app()
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
