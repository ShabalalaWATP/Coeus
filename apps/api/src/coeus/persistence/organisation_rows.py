"""Shared row decoding for organisation persistence adapters."""

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy.engine import RowMapping

from coeus.domain.organisation import OrganisationCategory, OrganisationUnit


def decode_unit(row: RowMapping | dict[str, object]) -> OrganisationUnit:
    return OrganisationUnit(
        UUID(str(row["unit_id"])),
        str(row["name"]),
        str(row["short_name"]),
        OrganisationCategory(str(row["category"])),
        None if row["parent_unit_id"] is None else UUID(str(row["parent_unit_id"])),
        cast(datetime, row["valid_from"]),
        cast(datetime | None, row["valid_until"]),
        str(row["time_zone"]),
        str(row["description"]),
        bool(row["is_active"]),
        int(str(row["version"])),
        str(row["provenance"]),
    )
