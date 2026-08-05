"""Deterministic dependency inventory for organisation split previews."""

import json
from hashlib import sha256
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from coeus.domain.organisation_merge import MergeAffectedRecord, MergeRecordKind
from coeus.domain.organisation_split import (
    OrganisationSplitConflict,
    OrganisationSplitImpact,
    OrganisationSplitRequest,
)


def inspect_split(
    connection: Connection, request: OrganisationSplitRequest
) -> OrganisationSplitImpact:
    values = {
        "source_id": request.source.unit_id,
        "parent_id": request.parent.unit_id,
        "successor_ids": [str(item.unit_id) for item in request.successors],
        "names": [item.name.casefold() for item in request.successors],
        "short_names": [item.short_name.casefold() for item in request.successors],
    }
    units = tuple(connection.execute(text(_UNITS), values).mappings())
    if len(units) != 2:
        raise OrganisationSplitConflict("the split source or parent is unavailable")
    if connection.execute(text(_SUCCESSOR_CONFLICT), values).first() is not None:
        raise OrganisationSplitConflict("a successor identity or sibling name already exists")
    records = tuple(_record(row) for row in connection.execute(text(_RECORDS), values).mappings())
    state = {
        "units": [
            {
                "unit_id": str(row["unit_id"]),
                "version": int(str(row["version"])),
                "is_active": bool(row["is_active"]),
                "parent_unit_id": None
                if row["parent_unit_id"] is None
                else str(row["parent_unit_id"]),
            }
            for row in units
        ],
        "records": [
            {
                "kind": item.kind.value,
                "record_id": str(item.record_id),
                "source_unit_id": str(item.source_unit_id),
                "version": item.version,
                "container_id": None if item.container_id is None else str(item.container_id),
            }
            for item in records
        ],
    }
    digest = sha256(json.dumps(state, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return OrganisationSplitImpact(records, 0, 0, 0, digest)


def _record(row: RowMapping) -> MergeAffectedRecord:
    return MergeAffectedRecord(
        MergeRecordKind(str(row["kind"])),
        UUID(str(row["record_id"])),
        UUID(str(row["source_unit_id"])),
        int(str(row["version"])),
        None if row["container_id"] is None else UUID(str(row["container_id"])),
    )


_UNITS = """
SELECT unit_id,version,is_active,parent_unit_id FROM organisation_units
WHERE unit_id IN (:source_id,:parent_id) ORDER BY unit_id
"""

_SUCCESSOR_CONFLICT = """
SELECT 1 FROM organisation_units WHERE unit_id=ANY(CAST(:successor_ids AS uuid[]))
 OR (parent_unit_id=:parent_id AND is_active AND
  (lower(name)=ANY(CAST(:names AS text[])) OR lower(short_name)=ANY(CAST(:short_names AS text[]))))
LIMIT 1
"""

_RECORDS = """
SELECT 'child_unit' kind,unit_id record_id,parent_unit_id source_unit_id,
 version,NULL::uuid container_id FROM organisation_units
WHERE parent_unit_id=:source_id AND is_active
UNION ALL
SELECT 'membership',membership_id,unit_id,version,NULL::uuid FROM team_memberships
WHERE unit_id=:source_id AND state='active'
 AND (valid_until IS NULL OR valid_until>transaction_timestamp())
UNION ALL
SELECT 'grant',grant_id,root_unit_id,version,NULL::uuid FROM team_management_grants
WHERE root_unit_id=:source_id AND revoked_at IS NULL
 AND (valid_until IS NULL OR valid_until>transaction_timestamp())
UNION ALL
SELECT 'delivery_profile',profile_id,unit_id,policy_version,NULL::uuid
FROM team_delivery_profiles WHERE unit_id=:source_id AND is_active
UNION ALL
SELECT 'capability',coverage.coverage_id,profile.unit_id,coverage.policy_version,
 profile.profile_id FROM team_capability_coverage coverage
JOIN team_delivery_profiles profile ON profile.profile_id=coverage.profile_id
WHERE profile.unit_id=:source_id
 AND (coverage.valid_until IS NULL OR coverage.valid_until>transaction_timestamp())
UNION ALL
SELECT 'task',ownership_id,owning_unit_id,version,NULL::uuid FROM team_task_ownership
WHERE owning_unit_id=:source_id AND state NOT IN ('completed','cancelled')
UNION ALL
SELECT 'pending_transfer',command_id,:source_id,1,NULL::uuid
FROM organisation_personnel_transfers WHERE status='pending'
 AND (source_unit_id=:source_id OR target_unit_id=:source_id)
ORDER BY kind,record_id
"""
