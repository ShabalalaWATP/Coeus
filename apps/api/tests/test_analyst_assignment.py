from types import SimpleNamespace
from typing import cast

from coeus.domain.tickets import ManagerRoutingDecisionStatus, RoutingRoute, TicketRecord
from coeus.services.analyst_assignment import (
    assignment_summary,
    normalise_team_name,
    normalise_titles,
    suggested_team_name,
)
from coeus.services.analyst_records import approved_route, default_work_package_titles


def test_normalises_assignment_titles_and_team_names() -> None:
    assert normalise_titles((" Review products ", "", "Draft", "Draft")) == (
        "Review products",
        "Draft",
    )
    assert normalise_team_name(None) is None
    assert normalise_team_name("  Maritime   Assessment  ") == "Maritime Assessment"


def test_suggests_assignment_team_from_latest_route_review() -> None:
    ticket = cast(
        TicketRecord,
        SimpleNamespace(
            rfa_reviews=(SimpleNamespace(suggested_team_name="RFA Cell"),),
            cm_reviews=(
                SimpleNamespace(suggested_collection_team_name="First CM Cell"),
                SimpleNamespace(suggested_collection_team_name="Latest CM Cell"),
            ),
        ),
    )

    assert suggested_team_name(ticket, RoutingRoute.RFA) == "RFA Cell"
    assert suggested_team_name(ticket, RoutingRoute.CM) == "Latest CM Cell"


def test_assignment_summary_mentions_team_when_present() -> None:
    assert assignment_summary(("analyst@example.test",), None) == "analyst@example.test"
    assert (
        assignment_summary(
            ("analyst@example.test", "analyst.4@example.test"), "Maritime Assessment"
        )
        == "analyst@example.test, analyst.4@example.test assigned via Maritime Assessment."
    )


def test_analyst_record_helpers_skip_rejected_routes_and_supply_default_work() -> None:
    ticket = cast(
        TicketRecord,
        SimpleNamespace(
            cm_reviews=(),
            manager_decisions=(
                SimpleNamespace(
                    status=ManagerRoutingDecisionStatus.REJECTED,
                    route=RoutingRoute.CM,
                ),
            ),
            rfa_reviews=(),
        ),
    )

    assert approved_route(ticket) is None
    assert default_work_package_titles(ticket, RoutingRoute.CM) == (
        "Prepare draft product",
        "Record supporting source trace",
    )
