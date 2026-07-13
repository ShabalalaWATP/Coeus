from datetime import UTC, datetime
from uuid import uuid4

import pytest

from coeus.domain.tickets import WorkflowPlanUpdate
from coeus.persistence.codec import CodecWriteFormat, decode_value, encode_value
from coeus.persistence.state_store import PostgresStateStore

pytestmark = pytest.mark.postgres


def test_postgres_round_trips_legacy_and_stable_codec_payloads(
    postgres_database_url: str,
) -> None:
    update = WorkflowPlanUpdate(
        update_id=uuid4(),
        ticket_id=uuid4(),
        title="Codec migration boundary",
        owner_role="JIOC",
        status="in_progress",
        note="Synthetic PostgreSQL fixture",
        created_at=datetime.now(UTC),
    )
    store = PostgresStateStore(postgres_database_url)
    store.save(
        "codec_fixture",
        {
            "legacy": encode_value(update, write_format=CodecWriteFormat.LEGACY),
            "stable": encode_value(update),
        },
    )

    restored = store.load("codec_fixture")

    assert restored is not None
    assert decode_value(restored["legacy"]) == update
    assert decode_value(restored["stable"]) == update
