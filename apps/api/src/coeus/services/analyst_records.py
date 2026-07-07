from datetime import UTC, datetime
from uuid import UUID, uuid4

from coeus.domain.tickets import (
    AnalystAssignment,
    AnalystWorkPackage,
    DraftProductAsset,
    DraftProductVersion,
    LinkedAnalystProduct,
    ManagerRoutingDecisionStatus,
    RoutingRoute,
    TicketRecord,
    WorkPackageStatus,
)


def latest_assignment(ticket: TicketRecord) -> AnalystAssignment | None:
    return ticket.analyst_assignments[-1] if ticket.analyst_assignments else None


def assigned_to(ticket: TicketRecord, analyst_user_id: UUID) -> bool:
    assignment = latest_assignment(ticket)
    return assignment is not None and assignment.analyst_user_id == analyst_user_id


def approved_route(ticket: TicketRecord) -> RoutingRoute | None:
    for decision in reversed(ticket.manager_decisions):
        if decision.status == ManagerRoutingDecisionStatus.APPROVED:
            return decision.route
    return None


def default_work_package_titles(ticket: TicketRecord, route: RoutingRoute) -> tuple[str, ...]:
    if route == RoutingRoute.RFA and ticket.rfa_reviews:
        titles = ticket.rfa_reviews[-1].suggested_work_packages
    elif route == RoutingRoute.CM and ticket.cm_reviews:
        titles = tuple(
            f"Collection tasking via {source}"
            for source in ticket.cm_reviews[-1].suggested_collection_sources
        )
    else:
        titles = ()
    return titles or ("Prepare draft product", "Record supporting source trace")


def assignment_record(
    ticket_id: UUID,
    analyst_user_id: UUID,
    assigned_by_user_id: UUID,
    route: RoutingRoute,
    team_name: str | None,
) -> AnalystAssignment:
    return AnalystAssignment(
        assignment_id=uuid4(),
        ticket_id=ticket_id,
        analyst_user_id=analyst_user_id,
        assigned_by_user_id=assigned_by_user_id,
        route=route,
        created_at=datetime.now(UTC),
        team_name=team_name,
    )


def work_package_records(
    ticket_id: UUID,
    titles: tuple[str, ...],
) -> tuple[AnalystWorkPackage, ...]:
    return tuple(
        AnalystWorkPackage(
            package_id=uuid4(),
            ticket_id=ticket_id,
            title=title,
            status=WorkPackageStatus.PENDING,
            sort_order=index,
            created_at=datetime.now(UTC),
        )
        for index, title in enumerate(titles, start=1)
    )


def next_draft_version(ticket: TicketRecord) -> int:
    return len(ticket.draft_products) + 1


def draft_version(
    ticket_id: UUID,
    version_number: int,
    title: str,
    summary: str,
    product_type: str,
    content: str,
    assets: tuple[DraftProductAsset, ...],
    created_by_user_id: UUID,
) -> DraftProductVersion:
    return DraftProductVersion(
        version_id=uuid4(),
        ticket_id=ticket_id,
        version_number=version_number,
        title=title,
        summary=summary,
        product_type=product_type,
        content=content,
        assets=assets,
        created_by_user_id=created_by_user_id,
        created_at=datetime.now(UTC),
    )


def all_work_packages_complete(ticket: TicketRecord) -> bool:
    return bool(ticket.work_packages) and all(
        package.status == WorkPackageStatus.COMPLETE for package in ticket.work_packages
    )


def linked_product_record(
    ticket_id: UUID,
    product_id: UUID,
    reference: str,
    title: str,
    summary: str,
    linked_by_user_id: UUID,
) -> LinkedAnalystProduct:
    return LinkedAnalystProduct(
        link_id=uuid4(),
        ticket_id=ticket_id,
        product_id=product_id,
        reference=reference,
        title=title,
        summary=summary,
        linked_by_user_id=linked_by_user_id,
        created_at=datetime.now(UTC),
    )
