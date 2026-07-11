from types import SimpleNamespace
from typing import cast
from uuid import uuid4

from coeus.domain.tickets import ManagerRoutingDecisionStatus, RoutingRoute, TicketRecord
from coeus.services.feedback_analytics import _approved_route, _route_scoped, _submission_for


def test_feedback_route_helpers_cover_empty_rejected_and_fallback_records() -> None:
    empty = cast(TicketRecord, SimpleNamespace(manager_decisions=(), feedback_submissions=()))
    fallback = cast(
        TicketRecord,
        SimpleNamespace(
            manager_decisions=(
                SimpleNamespace(
                    status=ManagerRoutingDecisionStatus.REJECTED,
                    route=RoutingRoute.CM,
                ),
            ),
            route_recommendations=(),
            feedback_submissions=(),
        ),
    )
    approved = cast(
        TicketRecord,
        SimpleNamespace(
            manager_decisions=(
                SimpleNamespace(
                    status=ManagerRoutingDecisionStatus.APPROVED,
                    route=RoutingRoute.RFA,
                ),
            ),
            route_recommendations=(),
            feedback_submissions=(),
        ),
    )

    assert _approved_route(empty) is None
    assert _route_scoped(fallback, RoutingRoute.CM)
    assert _route_scoped(approved, RoutingRoute.RFA)
    assert _submission_for(empty, uuid4()) is None
