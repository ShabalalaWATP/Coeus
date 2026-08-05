"""Deterministic dependency inventory for organisation merge previews."""

import json
from hashlib import sha256
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from coeus.domain.organisation_merge import (
    MergeAffectedRecord,
    MergeRecordKind,
    OrganisationMergeConflict,
    OrganisationMergeImpact,
    OrganisationMergeRequest,
)


def inspect_merge(
    connection: Connection, request: OrganisationMergeRequest
) -> OrganisationMergeImpact:
    source_ids = [str(item.unit_id) for item in request.sources]
    values = {"source_ids": source_ids, "successor_id": request.successor.unit_id}
    unit_rows = tuple(connection.execute(text(_UNITS), values).mappings())
    if len(unit_rows) != len(source_ids) + 1:
        raise OrganisationMergeConflict("an affected organisation unit is unavailable")
    rows = tuple(connection.execute(text(_RECORDS), values).mappings())
    records = tuple(_record(row) for row in rows)
    structural = connection.execute(text(_STRUCTURAL), values).mappings().one()
    active_children = int(str(structural["active_children"]))
    newly_covering_grants = int(str(structural["newly_covering_grants"]))
    maximum_result_depth = int(str(structural["maximum_result_depth"]))
    successor_profile = bool(connection.execute(text(_SUCCESSOR_PROFILE), values).scalar_one())
    state = {
        "units": [_state(row) for row in unit_rows],
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
        "active_children": active_children,
        "newly_covering_grants": newly_covering_grants,
        "maximum_result_depth": maximum_result_depth,
        "topology_state": str(structural["topology_state"]),
        "grant_state": str(structural["grant_state"]),
        "successor_has_delivery_profile": successor_profile,
    }
    digest = sha256(json.dumps(state, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return OrganisationMergeImpact(
        records,
        active_children,
        newly_covering_grants,
        maximum_result_depth,
        0,
        0,
        0,
        successor_profile,
        digest,
    )


def _record(row: RowMapping) -> MergeAffectedRecord:
    return MergeAffectedRecord(
        MergeRecordKind(str(row["kind"])),
        UUID(str(row["record_id"])),
        UUID(str(row["source_unit_id"])),
        int(str(row["version"])),
        None if row["container_id"] is None else UUID(str(row["container_id"])),
    )


def _state(row: RowMapping) -> dict[str, object]:
    return {
        "unit_id": str(row["unit_id"]),
        "version": int(str(row["version"])),
        "is_active": bool(row["is_active"]),
        "parent_unit_id": None if row["parent_unit_id"] is None else str(row["parent_unit_id"]),
    }


_UNITS = """
SELECT unit_id,version,is_active,parent_unit_id FROM organisation_units
WHERE unit_id=ANY(CAST(:source_ids AS uuid[])) OR unit_id=:successor_id
ORDER BY unit_id
"""

_STRUCTURAL = """
WITH children AS (
 SELECT unit_id FROM organisation_units
 WHERE parent_unit_id=ANY(CAST(:source_ids AS uuid[])) AND is_active
), target_ancestors AS (
 SELECT ancestor_unit_id,depth FROM organisation_unit_closure
 WHERE descendant_unit_id=:successor_id
), new_grants AS (
 SELECT DISTINCT grant_row.grant_id,child.unit_id child_id
 FROM team_management_grants grant_row CROSS JOIN children child
 WHERE grant_row.include_descendants AND grant_row.revoked_at IS NULL
  AND (grant_row.valid_until IS NULL OR grant_row.valid_until>transaction_timestamp())
  AND grant_row.root_unit_id IN (SELECT ancestor_unit_id FROM target_ancestors)
  AND NOT EXISTS (SELECT 1 FROM organisation_unit_closure current_scope
   WHERE current_scope.ancestor_unit_id=grant_row.root_unit_id
    AND current_scope.descendant_unit_id=child.unit_id)
)
SELECT (SELECT count(*) FROM children) active_children,
 (SELECT count(*) FROM new_grants) newly_covering_grants,
 COALESCE((SELECT max(depth) FROM target_ancestors),0) +
  CASE WHEN EXISTS(SELECT 1 FROM children) THEN 1 ELSE 0 END +
  COALESCE((SELECT max(closure.depth) FROM organisation_unit_closure closure
   WHERE closure.ancestor_unit_id IN (SELECT unit_id FROM children)),0) maximum_result_depth,
 COALESCE((SELECT string_agg(closure.ancestor_unit_id::text || ':' ||
  closure.descendant_unit_id::text || ':' || closure.depth::text,','
  ORDER BY closure.ancestor_unit_id,closure.depth,closure.descendant_unit_id)
  FROM organisation_unit_closure closure
  WHERE closure.ancestor_unit_id IN (SELECT unit_id FROM children)),'') topology_state,
 COALESCE((SELECT string_agg(grant_id::text || ':' || child_id::text,','
  ORDER BY grant_id,child_id) FROM new_grants),'') grant_state
"""

_SUCCESSOR_PROFILE = """
SELECT EXISTS(SELECT 1 FROM team_delivery_profiles
 WHERE unit_id=:successor_id AND is_active)
"""

_RECORDS = """
SELECT 'child_unit' kind,unit_id record_id,parent_unit_id source_unit_id,
 version,NULL::uuid container_id FROM organisation_units
WHERE parent_unit_id=ANY(CAST(:source_ids AS uuid[])) AND is_active
UNION ALL
SELECT 'membership' kind,membership_id record_id,unit_id source_unit_id,
 version,NULL::uuid container_id FROM team_memberships
WHERE unit_id=ANY(CAST(:source_ids AS uuid[])) AND state<>'cancelled'
 AND (valid_until IS NULL OR valid_until>transaction_timestamp())
UNION ALL
SELECT 'grant',grant_id,root_unit_id,version,NULL::uuid FROM team_management_grants
WHERE root_unit_id=ANY(CAST(:source_ids AS uuid[])) AND revoked_at IS NULL
 AND (valid_until IS NULL OR valid_until>transaction_timestamp())
UNION ALL
SELECT 'delivery_profile',profile_id,unit_id,policy_version,NULL::uuid
FROM team_delivery_profiles
WHERE unit_id=ANY(CAST(:source_ids AS uuid[])) AND is_active
UNION ALL
SELECT 'capability',coverage.coverage_id,profile.unit_id,coverage.policy_version,
 profile.profile_id FROM team_capability_coverage coverage
JOIN team_delivery_profiles profile ON profile.profile_id=coverage.profile_id
WHERE profile.unit_id=ANY(CAST(:source_ids AS uuid[]))
 AND (coverage.valid_until IS NULL OR coverage.valid_until>transaction_timestamp())
UNION ALL
SELECT 'task',ownership_id,owning_unit_id,version,NULL::uuid FROM team_task_ownership
WHERE owning_unit_id=ANY(CAST(:source_ids AS uuid[]))
 AND state NOT IN ('completed','cancelled')
UNION ALL
SELECT 'pending_transfer',command_id,
 CASE WHEN source_unit_id=ANY(CAST(:source_ids AS uuid[]))
      THEN source_unit_id ELSE target_unit_id END,1,NULL::uuid
FROM organisation_personnel_transfers
WHERE status='pending' AND (source_unit_id=ANY(CAST(:source_ids AS uuid[]))
 OR target_unit_id=ANY(CAST(:source_ids AS uuid[])))
ORDER BY kind,record_id
"""
