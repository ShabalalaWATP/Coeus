from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from coeus.api.dependencies import get_csrf_validated_session
from coeus.api.presenters.routing import ticket_response as to_routing_ticket_response
from coeus.api.presenters.tickets import to_ticket_response
from coeus.api.product_dependencies import get_customer_outcome_service
from coeus.domain.auth import AuthenticatedSession
from coeus.schemas.customer_outcomes import (
    CustomerProductDecisionRequest,
    JiocReanalysisDecisionRequest,
    ManagerReanalysisDecisionRequest,
)
from coeus.schemas.routing import RoutingTicketResponse
from coeus.schemas.tickets import TicketResponse
from coeus.services.customer_outcomes import CustomerOutcomeService

router = APIRouter(tags=["customer-outcomes"])


@router.post("/tickets/{ticket_id}/requirement-decision", response_model=TicketResponse)
async def decide_product_outcome(
    ticket_id: UUID,
    payload: CustomerProductDecisionRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    outcomes: Annotated[CustomerOutcomeService, Depends(get_customer_outcome_service)],
) -> TicketResponse:
    ticket = outcomes.customer_decision(
        authenticated.user,
        ticket_id,
        meets_requirement=payload.meets_requirement,
        reason=payload.reason,
        unmet_criteria=tuple(payload.unmet_criteria),
    )
    return to_ticket_response(ticket, authenticated.user)


@router.post(
    "/routing/{ticket_id}/reanalysis-manager-decision",
    response_model=RoutingTicketResponse,
)
async def decide_manager_reanalysis(
    ticket_id: UUID,
    payload: ManagerReanalysisDecisionRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    outcomes: Annotated[CustomerOutcomeService, Depends(get_customer_outcome_service)],
) -> RoutingTicketResponse:
    ticket = outcomes.manager_decision(
        authenticated.user,
        ticket_id,
        agree=payload.decision == "agree",
        rationale=payload.rationale,
    )
    return to_routing_ticket_response(ticket)


@router.post(
    "/routing/{ticket_id}/jioc-reanalysis-decision",
    response_model=RoutingTicketResponse,
)
async def decide_jioc_reanalysis(
    ticket_id: UUID,
    payload: JiocReanalysisDecisionRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    outcomes: Annotated[CustomerOutcomeService, Depends(get_customer_outcome_service)],
) -> RoutingTicketResponse:
    ticket = outcomes.jioc_decision(
        authenticated.user,
        ticket_id,
        reanalyse=payload.decision == "reanalyse",
        rationale=payload.rationale,
    )
    return to_routing_ticket_response(ticket)
