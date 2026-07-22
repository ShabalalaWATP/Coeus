from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

from coeus.api.presenters.qc import draft_response, product_response
from coeus.domain.enums import TicketState
from coeus.domain.product_submission import DraftProductAsset, DraftProductVersion
from coeus.domain.tickets import IntakeDetails, TicketRecord
from coeus.services.store import StoreServices


def test_qc_product_presenter_maps_empty_requirement_without_store_lookup() -> None:
    ticket = TicketRecord(
        ticket_id=uuid4(),
        reference="RFI-PRESENTER-1",
        requester_user_id=uuid4(),
        state=TicketState.QC_REVIEW,
        intake=IntakeDetails(),
    )

    response = product_response(ticket, cast(StoreServices, object()))

    assert response.title == "Untitled requirement"
    assert response.latest_draft is None
    assert response.ingested_product is None
    assert response.decisions == []
    assert response.checklist_keys


def test_qc_draft_presenter_maps_assets_and_preserves_order() -> None:
    ticket_id = uuid4()
    author_id = uuid4()
    first = DraftProductAsset(uuid4(), "first.pdf", "pdf", "application/pdf", 10, "a" * 64)
    second = DraftProductAsset(uuid4(), "second.csv", "csv", "text/csv", 20, "b" * 64)
    draft = DraftProductVersion(
        version_id=uuid4(),
        ticket_id=ticket_id,
        version_number=2,
        title="Synthetic assessment",
        summary="MOCK DATA ONLY",
        product_type="assessment",
        content="Synthetic content.",
        assets=(first, second),
        created_by_user_id=author_id,
        created_at=datetime.now(UTC),
    )

    response = draft_response(draft)

    assert response.version_number == 2
    assert [asset.name for asset in response.assets] == ["first.pdf", "second.csv"]
    assert response.assets[1].sha256 == "b" * 64
