from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from coeus.api.dependencies import (
    get_csrf_validated_session,
    get_current_session,
    get_ticket_collaborator_service,
    get_ticket_lifecycle_service,
    get_ticket_services,
    require_permission,
)
from coeus.api.presenters.tickets import (
    to_directory_response,
    to_ticket_response,
    to_ticket_summary_response,
)
from coeus.api.workflow_dependencies import (
    get_request_submission_service,
    get_tasking_consent_service,
)
from coeus.core.permissions import Permission
from coeus.core.resource_limits import DEFAULT_TICKET_PAGE_SIZE, MAX_TICKET_PAGE_SIZE
from coeus.domain.auth import AuthenticatedSession
from coeus.domain.tickets import CollaboratorAccess
from coeus.schemas.tickets import (
    AddInformationRequest,
    AttachmentMetadataRequest,
    ChatMessageRequest,
    CollaboratorAddRequest,
    CollectChoiceRequest,
    DirectoryResponse,
    IntakeUpdateRequest,
    NoMatchConsentRequest,
    TicketCancelRequest,
    TicketListResponse,
    TicketResponse,
)
from coeus.services.request_submission import RequestSubmissionService
from coeus.services.tasking_consent import TaskingConsentService
from coeus.services.ticket_collaborators import TicketCollaboratorService
from coeus.services.ticket_lifecycle import TicketLifecycleService
from coeus.services.tickets import TicketServices

router = APIRouter(tags=["tickets"])


@router.get("/tickets", response_model=TicketListResponse)
async def list_tickets(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    ticket_services: Annotated[TicketServices, Depends(get_ticket_services)],
    cursor: UUID | None = None,
    page_size: Annotated[
        int, Query(alias="pageSize", ge=1, le=MAX_TICKET_PAGE_SIZE)
    ] = DEFAULT_TICKET_PAGE_SIZE,
) -> TicketListResponse:
    page = ticket_services.tickets.list_visible_ticket_page(
        authenticated.user, cursor=cursor, page_size=page_size
    )
    return TicketListResponse(
        tickets=[to_ticket_summary_response(ticket, authenticated.user) for ticket in page.tickets],
        next_cursor=page.next_cursor,
    )


@router.get("/tickets/{ticket_id}", response_model=TicketResponse)
async def ticket_details(
    ticket_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    ticket_services: Annotated[TicketServices, Depends(get_ticket_services)],
) -> TicketResponse:
    ticket = ticket_services.tickets.get_visible_ticket(authenticated.user, ticket_id)
    return to_ticket_response(ticket, authenticated.user)


# Plain def so FastAPI runs this handler in the threadpool: the assistant
# reply may call the Gemini HTTP API synchronously and must not block the
# event loop.
@router.post("/chat/messages", response_model=TicketResponse, status_code=201)
def send_chat_message(
    payload: ChatMessageRequest,
    authenticated: Annotated[
        AuthenticatedSession,
        Depends(require_permission(Permission.CHAT_USE)),
    ],
    ticket_services: Annotated[TicketServices, Depends(get_ticket_services)],
    _csrf_session: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
) -> TicketResponse:
    ticket = ticket_services.conversations.send_message(
        authenticated.user,
        payload.message,
        payload.ticket_id,
    )
    return to_ticket_response(ticket, authenticated.user)


@router.post("/tickets/{ticket_id}/conversation/reopen", response_model=TicketResponse)
async def reopen_chat_conversation(
    ticket_id: UUID,
    authenticated: Annotated[
        AuthenticatedSession,
        Depends(require_permission(Permission.CHAT_USE)),
    ],
    ticket_services: Annotated[TicketServices, Depends(get_ticket_services)],
    _csrf_session: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
) -> TicketResponse:
    ticket = ticket_services.conversations.reopen(authenticated.user, ticket_id)
    return to_ticket_response(ticket, authenticated.user)


@router.patch("/tickets/{ticket_id}/intake", response_model=TicketResponse)
async def update_intake(
    ticket_id: UUID,
    payload: IntakeUpdateRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    ticket_services: Annotated[TicketServices, Depends(get_ticket_services)],
) -> TicketResponse:
    updates = payload.model_dump(exclude_unset=True)
    return to_ticket_response(
        ticket_services.tickets.update_intake(authenticated.user, ticket_id, updates),
        authenticated.user,
    )


@router.post("/tickets/{ticket_id}/attachments", response_model=TicketResponse)
async def add_attachment(
    ticket_id: UUID,
    payload: AttachmentMetadataRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    ticket_services: Annotated[TicketServices, Depends(get_ticket_services)],
) -> TicketResponse:
    ticket = ticket_services.tickets.add_attachment(
        authenticated.user,
        ticket_id,
        payload.name,
        payload.description,
        payload.source_type,
    )
    return to_ticket_response(ticket, authenticated.user)


@router.post("/tickets/{ticket_id}/submit", response_model=TicketResponse)
async def submit_ticket(
    ticket_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    submission: Annotated[RequestSubmissionService, Depends(get_request_submission_service)],
) -> TicketResponse:
    return to_ticket_response(
        await submission.submit(authenticated.user, ticket_id),
        authenticated.user,
    )


@router.get("/users/directory", response_model=DirectoryResponse)
async def user_directory(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    collaborators: Annotated[TicketCollaboratorService, Depends(get_ticket_collaborator_service)],
    q: Annotated[str, Query(min_length=3, max_length=254)],
) -> DirectoryResponse:
    return to_directory_response(collaborators.directory(authenticated.user, q))


@router.post("/tickets/{ticket_id}/collaborators", response_model=TicketResponse)
async def add_collaborator(
    ticket_id: UUID,
    payload: CollaboratorAddRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    collaborators: Annotated[TicketCollaboratorService, Depends(get_ticket_collaborator_service)],
) -> TicketResponse:
    ticket = collaborators.add(
        authenticated.user,
        ticket_id,
        payload.username,
        CollaboratorAccess(payload.access),
    )
    return to_ticket_response(ticket, authenticated.user)


@router.delete("/tickets/{ticket_id}/collaborators/{user_id}", response_model=TicketResponse)
async def remove_collaborator(
    ticket_id: UUID,
    user_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    collaborators: Annotated[TicketCollaboratorService, Depends(get_ticket_collaborator_service)],
) -> TicketResponse:
    return to_ticket_response(
        collaborators.remove(authenticated.user, ticket_id, user_id),
        authenticated.user,
    )


@router.post("/tickets/{ticket_id}/cancel", response_model=TicketResponse)
async def cancel_ticket(
    ticket_id: UUID,
    payload: TicketCancelRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    lifecycle: Annotated[TicketLifecycleService, Depends(get_ticket_lifecycle_service)],
) -> TicketResponse:
    return to_ticket_response(
        lifecycle.cancel(authenticated.user, ticket_id, payload.reason),
        authenticated.user,
    )


@router.post("/tickets/{ticket_id}/confirm-delivery", response_model=TicketResponse)
async def confirm_delivery(
    ticket_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    lifecycle: Annotated[TicketLifecycleService, Depends(get_ticket_lifecycle_service)],
) -> TicketResponse:
    return to_ticket_response(
        lifecycle.confirm_delivery(authenticated.user, ticket_id),
        authenticated.user,
    )


@router.post("/tickets/{ticket_id}/no-match-consent", response_model=TicketResponse)
async def no_match_consent(
    ticket_id: UUID,
    payload: NoMatchConsentRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    consent: Annotated[TaskingConsentService, Depends(get_tasking_consent_service)],
) -> TicketResponse:
    return to_ticket_response(
        consent.decide(authenticated.user, ticket_id, payload.task_as_new_request),
        authenticated.user,
    )


@router.post("/tickets/{ticket_id}/collect-choice", response_model=TicketResponse)
async def collect_choice(
    ticket_id: UUID,
    payload: CollectChoiceRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    lifecycle: Annotated[TicketLifecycleService, Depends(get_ticket_lifecycle_service)],
) -> TicketResponse:
    return to_ticket_response(
        lifecycle.collect_choice(authenticated.user, ticket_id, payload.analysed),
        authenticated.user,
    )


@router.post("/tickets/{ticket_id}/timeline", response_model=TicketResponse)
async def add_information(
    ticket_id: UUID,
    payload: AddInformationRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    ticket_services: Annotated[TicketServices, Depends(get_ticket_services)],
) -> TicketResponse:
    ticket = ticket_services.tickets.add_information(authenticated.user, ticket_id, payload.body)
    return to_ticket_response(ticket, authenticated.user)
