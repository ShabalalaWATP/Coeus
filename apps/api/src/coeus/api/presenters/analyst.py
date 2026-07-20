from coeus.domain.auth import UserAccount
from coeus.domain.tickets import (
    AnalystAssignment,
    AnalystNote,
    AnalystWorkPackage,
    DraftProductAsset,
    DraftProductVersion,
    LinkedAnalystProduct,
    TicketRecord,
)
from coeus.schemas.analyst import (
    AnalystAssignmentResponse,
    AnalystCandidateResponse,
    AnalystNoteResponse,
    AnalystTaskResponse,
    DraftAssetResponse,
    DraftProductResponse,
    LinkedProductResponse,
    WorkPackageResponse,
)
from coeus.schemas.tickets import ChatMessageResponse
from coeus.services.analyst_records import active_assignments
from coeus.services.analyst_workflow import AnalystWorkflowService


def candidate_response(user: UserAccount) -> AnalystCandidateResponse:
    return AnalystCandidateResponse(
        user_id=user.user_id,
        username=user.username,
        display_name=user.display_name,
    )


def task_response(
    ticket: TicketRecord, actor: UserAccount, analyst: AnalystWorkflowService
) -> AnalystTaskResponse:
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
        assignments=[_assignment_response(item) for item in active_assignments(ticket)],
        work_packages=[_work_package_response(item) for item in ticket.work_packages],
        notes=[_note_response(item) for item in ticket.analyst_notes],
        linked_products=[
            _linked_product_response(item)
            for item in analyst.visible_linked_products(actor, ticket)
        ],
        drafts=[_draft_response(item) for item in ticket.draft_products],
    )


def conversation_response(ticket: TicketRecord) -> list[ChatMessageResponse]:
    return [
        ChatMessageResponse(
            message_id=message.message_id,
            author=message.author,
            body=message.body,
            created_at=message.created_at,
        )
        for message in ticket.messages
    ]


def _assignment_response(assignment: AnalystAssignment) -> AnalystAssignmentResponse:
    return AnalystAssignmentResponse(
        assignment_id=assignment.assignment_id,
        analyst_user_id=assignment.analyst_user_id,
        assigned_by_user_id=assignment.assigned_by_user_id,
        route=assignment.route.value,
        created_at=assignment.created_at,
        team_id=assignment.team_id,
        team_name=assignment.team_name,
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
        description=draft.description or draft.content,
        source_type=draft.source_type,
        owner_team=draft.owner_team,
        area_or_region=draft.area_or_region,
        classification_level=draft.classification_level,
        releasability=list(draft.releasability),
        handling_caveats=list(draft.handling_caveats),
        tags=list(draft.tags),
        acg_ids=list(draft.acg_ids),
        manifest_hash=draft.manifest_hash,
        assets=[_draft_asset_response(item) for item in draft.assets],
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
        detected_mime_type=asset.detected_mime_type or asset.mime_type,
        preview_kind=asset.preview_kind,
        processing_status=asset.processing_status,
        preview_available=bool(asset.object_key),
    )
