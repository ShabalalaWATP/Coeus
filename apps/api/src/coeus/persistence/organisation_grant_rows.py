"""Grant-row decoding and authority-specific relational reads."""

from datetime import datetime
from enum import StrEnum
from typing import cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine, RowMapping

from coeus.domain.organisation import ManagementAction, OrganisationManagementGrant


def decode_grant(row: RowMapping) -> OrganisationManagementGrant:
    source = row["source_grant_id"]
    return OrganisationManagementGrant(
        UUID(str(row["grant_id"])),
        UUID(str(row["manager_user_id"])),
        UUID(str(row["root_unit_id"])),
        ManagementAction(str(row["action"])),
        bool(row["include_descendants"]),
        cast(datetime, row["valid_from"]),
        UUID(str(row["created_by_user_id"])),
        str(row["reason"]),
        cast(datetime | None, row["valid_until"]),
        cast(datetime | None, row["revoked_at"]),
        None if source is None else UUID(str(source)),
        int(str(row["delegation_depth"])),
        int(str(row["version"])),
        _uuid(row.get("revoked_by_user_id")),
        str(row.get("revocation_reason") or ""),
    )


def get_grant(engine: Engine, grant_id: UUID) -> OrganisationManagementGrant | None:
    with engine.begin() as connection:
        row = (
            connection.execute(
                text("SELECT * FROM team_management_grants WHERE grant_id = :grant_id"),
                {"grant_id": grant_id},
            )
            .mappings()
            .first()
        )
    return None if row is None else decode_grant(row)


def unit_is_within(engine: Engine, root_unit_id: UUID, target_unit_id: UUID) -> bool:
    with engine.begin() as connection:
        found = connection.execute(
            text(
                "SELECT 1 FROM organisation_unit_closure WHERE ancestor_unit_id = "
                ":root_unit_id AND descendant_unit_id = :target_unit_id LIMIT 1"
            ),
            {"root_unit_id": root_unit_id, "target_unit_id": target_unit_id},
        ).first()
    return found is not None


def dataclass_params(value: object) -> dict[str, object]:
    return {
        key: item.value if isinstance(item, StrEnum) else item for key, item in vars(value).items()
    }


def _uuid(value: object) -> UUID | None:
    return None if value is None else UUID(str(value))
