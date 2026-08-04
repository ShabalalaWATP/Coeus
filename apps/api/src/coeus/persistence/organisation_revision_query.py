"""Immutable organisation topology revision insertion helpers."""

from enum import StrEnum
from typing import cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from coeus.domain.organisation import OrganisationTopologyRevision
from coeus.persistence import organisation_postgres_sql as sql


def insert_revision(connection: Connection, revision: OrganisationTopologyRevision) -> None:
    inserted = connection.execute(text(sql.INSERT_REVISION), _params(revision)).first()
    if inserted is not None:
        return
    existing = (
        connection.execute(
            text(
                "SELECT unit_id, parent_unit_id, path, valid_from, valid_until, "
                "change_command_id, changed_by_user_id FROM organisation_topology_revisions "
                "WHERE revision_id = :revision_id"
            ),
            {"revision_id": revision.revision_id},
        )
        .mappings()
        .one()
    )
    if not _same_revision(existing, revision):
        raise ValueError("topology revision identity is already in use")


def _params(value: object) -> dict[str, object]:
    output: dict[str, object] = {}
    for key, item in vars(value).items():
        if isinstance(item, StrEnum):
            output[key] = item.value
        elif isinstance(item, tuple) and all(isinstance(part, UUID) for part in item):
            output[key] = list(item)
        else:
            output[key] = item
    return output


def _same_revision(row: RowMapping, revision: OrganisationTopologyRevision) -> bool:
    stored_path = tuple(UUID(str(value)) for value in cast(list[object], row["path"]))
    return (
        UUID(str(row["unit_id"])) == revision.unit_id
        and _uuid(row["parent_unit_id"]) == revision.parent_unit_id
        and stored_path == revision.path
        and row["valid_from"] == revision.valid_from
        and row["valid_until"] == revision.valid_until
        and UUID(str(row["change_command_id"])) == revision.change_command_id
        and UUID(str(row["changed_by_user_id"])) == revision.changed_by_user_id
    )


def _uuid(value: object) -> UUID | None:
    return None if value is None else UUID(str(value))
