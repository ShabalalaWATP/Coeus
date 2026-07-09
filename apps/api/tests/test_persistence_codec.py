from datetime import UTC, datetime
from uuid import uuid4

from coeus.core.permissions import Permission
from coeus.domain.access import ProductStatus
from coeus.domain.enums import TicketState
from coeus.domain.store import StoreProductMetadata
from coeus.domain.tickets import IntakeDetails, TicketRecord, WorkflowPlanUpdate
from coeus.persistence.codec import decode_value, encode_value


def test_workflow_plan_update_round_trips() -> None:
    update = WorkflowPlanUpdate(
        update_id=uuid4(),
        ticket_id=uuid4(),
        title="Confirm collection tasking",
        owner_role="Collection Manager",
        status="in_progress",
        note="Awaiting source availability confirmation.",
        created_at=datetime.now(UTC),
    )

    decoded = decode_value(encode_value(update))

    assert decoded == update


def test_legacy_project_permissions_are_dropped_from_decoded_sets() -> None:
    encoded = {
        "__frozenset__": [
            {
                "__enum__": "coeus.core.permissions.Permission",
                "value": "project:read",
            },
            {
                "__enum__": "coeus.core.permissions.Permission",
                "value": Permission.TICKET_CREATE.value,
            },
        ]
    }

    decoded = decode_value(encoded)

    assert decoded == frozenset({Permission.TICKET_CREATE})


def test_legacy_project_plan_update_decodes_as_workflow_plan_update() -> None:
    update = WorkflowPlanUpdate(
        update_id=uuid4(),
        ticket_id=uuid4(),
        title="Confirm collection tasking",
        owner_role="Collection Manager",
        status="in_progress",
        note="Awaiting source availability confirmation.",
        created_at=datetime.now(UTC),
    )
    encoded = encode_value(update)
    encoded["__type__"] = "coeus.domain.tickets.ProjectPlanUpdate"

    decoded = decode_value(encoded)

    assert decoded == update


def test_legacy_ticket_project_plan_updates_decode_as_workflow_plan_updates() -> None:
    requester = uuid4()
    update = WorkflowPlanUpdate(
        update_id=uuid4(),
        ticket_id=uuid4(),
        title="Confirm collection tasking",
        owner_role="Collection Manager",
        status="in_progress",
        note="Awaiting source availability confirmation.",
        created_at=datetime.now(UTC),
    )
    ticket = TicketRecord(
        ticket_id=update.ticket_id,
        reference="TCK-LEGACY",
        requester_user_id=requester,
        state=TicketState.ROUTE_ASSESSMENT,
        intake=IntakeDetails(title="Legacy"),
        workflow_plan_updates=(update,),
    )
    encoded = encode_value(ticket)
    encoded["fields"]["project_plan_updates"] = encoded["fields"].pop("workflow_plan_updates")
    encoded["fields"]["suggested_project_name"] = "Retired workspace"

    decoded = decode_value(encoded)

    assert decoded == ticket


def test_store_metadata_decoder_ignores_retired_project_id() -> None:
    metadata = StoreProductMetadata(
        title="Test",
        summary="Test",
        description="Test",
        product_type="assessment_report",
        source_type="finished_assessment",
        owner_team="RFA",
        area_or_region="Baltic ports",
        classification_level=1,
        releasability=frozenset({"MOCK"}),
        handling_caveats=frozenset({"MOCK DATA ONLY"}),
        tags=frozenset({"baltic"}),
        acg_ids=frozenset({uuid4()}),
        status=ProductStatus.PUBLISHED,
        time_period_start=None,
        time_period_end=None,
        geojson_ref=None,
        bounding_box=None,
    )
    encoded = encode_value(metadata)
    encoded["fields"]["project_id"] = {"__uuid__": str(uuid4())}

    decoded = decode_value(encoded)

    assert decoded == metadata
