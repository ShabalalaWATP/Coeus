from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.engine import RowMapping

from coeus.domain.organisation import (
    OrganisationCategory,
    OrganisationTopologyRevision,
    OrganisationUnit,
)
from coeus.persistence.organisation_postgres import _uuid
from coeus.persistence.organisation_revision_query import _same_revision, insert_revision
from test_organisation_postgres_unit import Connection, Result, _repository

NOW = datetime(2026, 8, 3, 8, tzinfo=UTC)


def test_unit_upsert_rejects_reparent_missing_direct_path_and_revision_collision() -> None:
    actor_id, parent_id = uuid4(), uuid4()
    unit = OrganisationUnit(
        uuid4(), "Synthetic Child", "Child", OrganisationCategory.BRANCH, parent_id, NOW
    )
    revision = OrganisationTopologyRevision(
        uuid4(), unit.unit_id, parent_id, (parent_id, unit.unit_id), NOW, uuid4(), actor_id
    )
    repository, _ = _repository(
        Result(scalars=[parent_id]), Result(first={"parent_unit_id": uuid4()})
    )
    with pytest.raises(ValueError, match="cannot reparent"):
        repository.upsert_unit(unit, revision)
    repository, _ = _repository(
        Result(scalars=[parent_id]),
        Result(first=None),
        Result(),
        Result(),
        Result(),
        Result(first=None),
    )
    with pytest.raises(ValueError, match="missing or exceeds"):
        repository.upsert_unit(unit, revision)

    stored = {
        "unit_id": unit.unit_id,
        "parent_unit_id": parent_id,
        "path": [parent_id, unit.unit_id],
        "valid_from": NOW,
        "valid_until": None,
        "change_command_id": revision.change_command_id,
        "changed_by_user_id": revision.changed_by_user_id,
    }
    connection = Connection(Result(first=None), Result(rows=[stored]))
    insert_revision(cast(object, connection), revision)  # type: ignore[arg-type]
    assert _same_revision(cast(RowMapping, stored), revision)
    stored["unit_id"] = uuid4()
    connection = Connection(Result(first=None), Result(rows=[stored]))
    with pytest.raises(ValueError, match="identity is already in use"):
        insert_revision(cast(object, connection), revision)  # type: ignore[arg-type]
    assert _uuid(None) is None
