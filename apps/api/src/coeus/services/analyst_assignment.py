from dataclasses import dataclass, replace
from uuid import UUID

from coeus.domain.auth import UserAccount
from coeus.domain.enums import TicketState
from coeus.domain.tickets import RoutingRoute, TicketRecord
from coeus.services.analyst_records import (
    assignment_record,
    default_work_package_titles,
    work_package_records,
)
from coeus.services.ticket_records import timeline


@dataclass(frozen=True)
class AssignmentChange:
    ticket: TicketRecord
    event_type: str
    audit_metadata: dict[str, str]


def normalise_titles(titles: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(title.strip() for title in titles if title.strip()))


def normalise_team_name(team_name: str | None) -> str | None:
    if team_name is None:
        return None
    cleaned = " ".join(team_name.split())
    return cleaned[:120] or None


def suggested_team_name(ticket: TicketRecord, route: RoutingRoute) -> str | None:
    if route == RoutingRoute.RFA and ticket.rfa_reviews:
        return ticket.rfa_reviews[-1].suggested_team_name
    if route == RoutingRoute.CM and ticket.cm_reviews:
        return ticket.cm_reviews[-1].suggested_collection_team_name
    return None


def assignment_summary(username: str, team_name: str | None) -> str:
    if team_name:
        return f"{username} assigned via {team_name}."
    return username


def assignment_change(
    ticket: TicketRecord,
    actor: UserAccount,
    analyst: UserAccount,
    route: RoutingRoute,
    work_package_titles: tuple[str, ...],
    team_name: str | None,
    *,
    reassignment: bool,
) -> AssignmentChange:
    titles = normalise_titles(work_package_titles) or default_work_package_titles(ticket, route)
    assignment_team = normalise_team_name(team_name) or suggested_team_name(ticket, route)
    event_type = "analyst_reassigned" if reassignment else "analyst_assigned"
    assignment = assignment_record(
        ticket.ticket_id, analyst.user_id, actor.user_id, route, assignment_team
    )
    packages = () if reassignment else work_package_records(ticket.ticket_id, titles)
    metadata = assignment_metadata(ticket.ticket_id, analyst.user_id, assignment_team)
    return AssignmentChange(
        ticket=replace(
            ticket,
            state=TicketState.ANALYST_IN_PROGRESS,
            analyst_assignments=(*ticket.analyst_assignments, assignment),
            work_packages=(*ticket.work_packages, *packages),
            timeline=(
                *ticket.timeline,
                timeline(
                    ticket.ticket_id,
                    actor.user_id,
                    event_type,
                    assignment_summary(analyst.username, assignment_team),
                ),
            ),
        ),
        event_type=event_type,
        audit_metadata=metadata,
    )


def assignment_metadata(
    ticket_id: UUID, analyst_user_id: UUID, team_name: str | None
) -> dict[str, str]:
    metadata = {
        "ticket_id": str(ticket_id),
        "analyst_user_id": str(analyst_user_id),
    }
    if team_name:
        metadata["team_name"] = team_name
    return metadata
