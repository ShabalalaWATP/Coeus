"""Object kinds a workspace record may reference at all."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from coeus.domain.workspace_productivity import WorkspaceRecordDenied
from coeus.persistence.workspace_productivity_authority import (
    require_link_source,
    require_update_object,
)

AT = datetime(2026, 8, 4, 12, tzinfo=UTC)


@pytest.mark.parametrize("object_type", ["person", "product", "", "TICKET"])
def test_an_unknown_update_object_kind_is_refused_before_any_lookup(object_type: str) -> None:
    with pytest.raises(WorkspaceRecordDenied):
        require_update_object(
            object(),  # type: ignore[arg-type]
            uuid4(),
            uuid4(),
            object_type,
            uuid4(),
            AT,
        )


@pytest.mark.parametrize("source_type", ["calendar", "grant", "product", ""])
def test_only_a_ticket_or_work_package_may_anchor_a_store_link(source_type: str) -> None:
    with pytest.raises(WorkspaceRecordDenied):
        require_link_source(
            object(),  # type: ignore[arg-type]
            uuid4(),
            uuid4(),
            source_type,
            uuid4(),
            AT,
        )
