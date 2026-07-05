from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from coeus.api.dependencies import (
    get_analyst_workflow_service,
    get_csrf_validated_session,
    get_current_session,
)
from coeus.domain.auth import AuthenticatedSession, UserAccount
from coeus.domain.tickets import (
    AnalystAssignment,
    AnalystNote,
    AnalystWorkPackage,
    DraftProductAsset,
    DraftProductVersion,
    LinkedAnalystProduct,
    TicketRecord,
    WorkPackageStatus,
)
from coeus.schemas.analyst import (
    AnalystAssignmentRequest,
    AnalystAssignmentResponse,
    AnalystCandidateListResponse,
    AnalystCandidateResponse,
    AnalystNoteRequest,
    AnalystNoteResponse,
    AnalystTaskListResponse,
    AnalystTaskResponse,
    DraftAssetRequest,
    DraftAssetResponse,
    DraftProductRequest,
    DraftProductResponse,
    LinkedProductResponse,
    LinkProductRequest,
    WorkPackageResponse,
    WorkPackageUpdateRequest,
)
from coeus.services.analyst_records import latest_assignment
from coeus.services.analyst_workflow import (
    AnalystWorkflowService,
    DraftAssetInput,
    DraftProductInput,
)

router = APIRouter(prefix="/analyst", tags=["analyst"])


@router.get("/candidates", response_model=AnalystCandidateListResponse)
async def analyst_candidates(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    analyst: Annotated[AnalystWorkflowService, Depends(get_analyst_workflow_service)],
) -> AnalystCandidateListResponse:
    return AnalystCandidateListResponse(
        analysts=[
            _candidate_response(user) for user in analyst.analyst_candidates(authenticated.user)
        ]
    )


@router.get("/tasks", response_model=AnalystTaskListResponse)
async def analyst_tasks(
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    analyst: Annotated[AnalystWorkflowService, Depends(get_analyst_workflow_service)],
) -> AnalystTaskListResponse:
    return AnalystTaskListResponse(
        tasks=[_task_response(ticket) for ticket in analyst.list_tasks(authenticated.user)]
    )


@router.get("/tasks/{ticket_id}", response_model=AnalystTaskResponse)
async def analyst_task_details(
    ticket_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_current_session)],
    analyst: Annotated[AnalystWorkflowService, Depends(get_analyst_workflow_service)],
) -> AnalystTaskResponse:
    return _task_response(analyst.task_details(authenticated.user, ticket_id))


@router.post("/tasks/{ticket_id}/assign", response_model=AnalystTaskResponse)
async def assign_analyst(
    ticket_id: UUID,
    payload: AnalystAssignmentRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    analyst: Annotated[AnalystWorkflowService, Depends(get_analyst_workflow_service)],
) -> AnalystTaskResponse:
    return _task_response(
        analyst.assign(
            authenticated.user,
            ticket_id,
            payload.analyst_user_id,
            tuple(payload.work_packages),
        )
    )


@router.post("/tasks/{ticket_id}/notes", response_model=AnalystTaskResponse)
async def add_note(
    ticket_id: UUID,
    payload: AnalystNoteRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    analyst: Annotated[AnalystWorkflowService, Depends(get_analyst_workflow_service)],
) -> AnalystTaskResponse:
    return _task_response(analyst.add_note(authenticated.user, ticket_id, payload.body))


@router.post("/tasks/{ticket_id}/products", response_model=AnalystTaskResponse)
async def link_product(
    ticket_id: UUID,
    payload: LinkProductRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    analyst: Annotated[AnalystWorkflowService, Depends(get_analyst_workflow_service)],
) -> AnalystTaskResponse:
    return _task_response(analyst.link_product(authenticated.user, ticket_id, payload.product_id))


@router.patch("/tasks/{ticket_id}/work-packages/{package_id}", response_model=AnalystTaskResponse)
async def update_work_package(
    ticket_id: UUID,
    package_id: UUID,
    payload: WorkPackageUpdateRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    analyst: Annotated[AnalystWorkflowService, Depends(get_analyst_workflow_service)],
) -> AnalystTaskResponse:
    return _task_response(
        analyst.update_work_package(
            authenticated.user,
            ticket_id,
            package_id,
            WorkPackageStatus(payload.status),
        )
    )


@router.post("/tasks/{ticket_id}/drafts", response_model=AnalystTaskResponse)
async def save_draft(
    ticket_id: UUID,
    payload: DraftProductRequest,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    analyst: Annotated[AnalystWorkflowService, Depends(get_analyst_workflow_service)],
) -> AnalystTaskResponse:
    return _task_response(
        analyst.create_draft(authenticated.user, ticket_id, _draft_input(payload))
    )


@router.post("/tasks/{ticket_id}/submit-qc", response_model=AnalystTaskResponse)
async def submit_to_qc(
    ticket_id: UUID,
    authenticated: Annotated[AuthenticatedSession, Depends(get_csrf_validated_session)],
    analyst: Annotated[AnalystWorkflowService, Depends(get_analyst_workflow_service)],
) -> AnalystTaskResponse:
    return _task_response(analyst.submit_to_qc(authenticated.user, ticket_id))


def _candidate_response(user: UserAccount) -> AnalystCandidateResponse:
    return AnalystCandidateResponse(
        user_id=user.user_id,
        username=user.username,
        display_name=user.display_name,
    )


def _task_response(ticket: TicketRecord) -> AnalystTaskResponse:
    intake = ticket.intake
    return AnalystTaskResponse(
        ticket_id=ticket.ticket_id,
        reference=ticket.reference,
        state=ticket.state.value,
        title=intake.title or "Untitled requirement",
        description=intake.description,
        operational_question=intake.operational_question,
        area_or_region=intake.area_or_region,
        priority=intake.priority,
        required_output_format=intake.required_output_format,
        chat_summary=[message.body for message in ticket.messages[-4:]],
        manager_notes=[decision.reason for decision in ticket.manager_decisions],
        assignment=_assignment_response(latest_assignment(ticket)),
        work_packages=[_work_package_response(package) for package in ticket.work_packages],
        notes=[_note_response(note) for note in ticket.analyst_notes],
        linked_products=[_linked_product_response(link) for link in ticket.linked_products],
        drafts=[_draft_response(draft) for draft in ticket.draft_products],
    )


def _assignment_response(
    assignment: AnalystAssignment | None,
) -> AnalystAssignmentResponse | None:
    if assignment is None:
        return None
    return AnalystAssignmentResponse(
        assignment_id=assignment.assignment_id,
        analyst_user_id=assignment.analyst_user_id,
        assigned_by_user_id=assignment.assigned_by_user_id,
        route=assignment.route.value,
        created_at=assignment.created_at,
    )


def _work_package_response(package: AnalystWorkPackage) -> WorkPackageResponse:
    return WorkPackageResponse(
        package_id=package.package_id,
        title=package.title,
        status=package.status.value,
        sort_order=package.sort_order,
    )


def _note_response(note: AnalystNote) -> AnalystNoteResponse:
    return AnalystNoteResponse(
        note_id=note.note_id,
        body=note.body,
        created_by_user_id=note.created_by_user_id,
        created_at=note.created_at,
    )


def _linked_product_response(link: LinkedAnalystProduct) -> LinkedProductResponse:
    return LinkedProductResponse(
        link_id=link.link_id,
        product_id=link.product_id,
        reference=link.reference,
        title=link.title,
        summary=link.summary,
        created_at=link.created_at,
    )


def _draft_response(draft: DraftProductVersion) -> DraftProductResponse:
    return DraftProductResponse(
        version_id=draft.version_id,
        version_number=draft.version_number,
        title=draft.title,
        summary=draft.summary,
        product_type=draft.product_type,
        content=draft.content,
        assets=[_draft_asset_response(asset) for asset in draft.assets],
        created_at=draft.created_at,
    )


def _draft_asset_response(asset: DraftProductAsset) -> DraftAssetResponse:
    return DraftAssetResponse(
        asset_id=asset.asset_id,
        name=asset.name,
        asset_type=asset.asset_type,
        mime_type=asset.mime_type,
        size_bytes=asset.size_bytes,
        sha256=asset.sha256,
    )


def _draft_input(payload: DraftProductRequest) -> DraftProductInput:
    return DraftProductInput(
        title=payload.title,
        summary=payload.summary,
        product_type=payload.product_type,
        content=payload.content,
        assets=tuple(_asset_input(asset) for asset in payload.assets),
    )


def _asset_input(asset: DraftAssetRequest) -> DraftAssetInput:
    return DraftAssetInput(
        name=asset.name,
        asset_type=asset.asset_type,
        mime_type=asset.mime_type,
        size_bytes=asset.size_bytes,
        sha256=asset.sha256,
    )
