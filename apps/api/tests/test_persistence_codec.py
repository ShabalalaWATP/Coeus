from datetime import UTC, datetime
from uuid import uuid4

from coeus.domain.access import ProductStatus
from coeus.domain.store import StoreProductMetadata
from coeus.domain.tickets import ProjectPlanUpdate
from coeus.persistence.codec import decode_value, encode_value


def test_project_plan_update_round_trips() -> None:
    update = ProjectPlanUpdate(
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
