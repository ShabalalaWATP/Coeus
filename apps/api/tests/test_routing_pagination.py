from typing import cast

from coeus.api.routes.routing import QUEUE_PAGE_SIZE, _queue_page
from coeus.domain.tickets import TicketRecord


def test_routing_queue_page_is_bounded_and_continuable() -> None:
    tickets = cast(tuple[TicketRecord, ...], tuple(range(QUEUE_PAGE_SIZE + 3)))

    first, cursor = _queue_page(tickets, 0, QUEUE_PAGE_SIZE)
    second, final_cursor = _queue_page(tickets, int(cursor or "0"), QUEUE_PAGE_SIZE)

    assert len(first) == QUEUE_PAGE_SIZE
    assert second == tickets[QUEUE_PAGE_SIZE:]
    assert final_cursor is None
    assert set(first).isdisjoint(second)
