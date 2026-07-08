from coeus.domain.tickets import RoutingRoute, TicketRecord


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
