"""Bounded SQL and evidence helpers for assignment recommendations."""

import json
from collections import Counter
from datetime import datetime
from hashlib import sha256
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from coeus.domain.assignment_recommendations import ExclusionCode
from coeus.domain.organisation import ManagementAction
from coeus.domain.organisation_authority import OrganisationAuthorityDenied
from coeus.domain.team_task_ownership import WorkflowLeg
from coeus.persistence.organisation_authority_validation import validate_lineage


def authorised_units(
    connection: Connection,
    actor_id: UUID,
    workflow_leg: WorkflowLeg,
    at: datetime,
    requested_unit_id: UUID | None,
) -> tuple[UUID, ...]:
    rows = tuple(
        connection.execute(
            text(_AUTHORISED_UNITS),
            {
                "actor_id": actor_id,
                "route": "rfa" if workflow_leg is WorkflowLeg.RFA else "cm",
                "at": at,
                "unit_id": requested_unit_id,
            },
        ).mappings()
    )
    valid: set[UUID] = set()
    for row in rows:
        unit_id = UUID(str(row["unit_id"]))
        try:
            validate_lineage(
                connection,
                UUID(str(row["grant_id"])),
                actor_id,
                unit_id,
                ManagementAction.TASK_ASSIGN,
                at,
            )
            valid.add(unit_id)
        except OrganisationAuthorityDenied:
            continue
    if requested_unit_id is not None and requested_unit_id not in valid:
        return ()
    return tuple(sorted(valid, key=str))


def roster_rows(
    connection: Connection,
    unit_ids: tuple[UUID, ...],
    start: datetime,
    deadline: datetime,
) -> tuple[RowMapping, ...]:
    if not unit_ids:
        return ()
    return tuple(
        connection.execute(
            text(_ROSTER),
            {"unit_ids": list(unit_ids), "start": start, "deadline": deadline},
        ).mappings()
    )


def capability_counts(
    connection: Connection,
    unit_ids: tuple[UUID, ...],
    user_ids: tuple[UUID, ...],
    capability_ids: tuple[str, ...],
    start: datetime,
    deadline: datetime,
) -> tuple[dict[UUID, int], dict[UUID, int]]:
    team = {
        UUID(str(row["unit_id"])): int(row["matched"])
        for row in connection.execute(
            text(_TEAM_CAPABILITIES),
            {
                "unit_ids": list(unit_ids),
                "capabilities": list(capability_ids),
                "start": start,
                "deadline": deadline,
            },
        ).mappings()
    }
    people = {
        UUID(str(row["user_id"])): int(row["matched"])
        for row in connection.execute(
            text(_PERSON_COMPETENCIES),
            {
                "user_ids": list(user_ids),
                "capabilities": list(capability_ids),
                "start": start,
                "deadline": deadline,
            },
        ).mappings()
    }
    return team, people


def active_team_hold_minutes(
    connection: Connection,
    unit_id: UUID,
    start: datetime,
    deadline: datetime,
    at: datetime,
    exclude_recommendation_id: UUID | None = None,
) -> int:
    return int(
        connection.execute(
            text(_ACTIVE_HOLDS),
            {
                "unit_id": unit_id,
                "start": start,
                "deadline": deadline,
                "at": at,
                "exclude_id": exclude_recommendation_id,
            },
        ).scalar_one()
        or 0
    )


def evidence_hash(values: dict[str, object]) -> str:
    return sha256(json.dumps(values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def exclusion_pairs(counts: Counter[ExclusionCode]) -> tuple[tuple[ExclusionCode, int], ...]:
    return tuple((code, counts[code]) for code in ExclusionCode if counts[code])


_AUTHORISED_UNITS = """
SELECT management_grant.grant_id,unit.unit_id
FROM team_management_grants management_grant
JOIN organisation_units unit ON unit.is_active
JOIN team_delivery_profiles profile ON profile.unit_id=unit.unit_id AND profile.is_active
WHERE management_grant.manager_user_id=:actor_id AND management_grant.action='task:assign'
  AND profile.route=:route
  AND (:unit_id IS NULL OR unit.unit_id=:unit_id)
  AND unit.valid_from<=:at AND (unit.valid_until IS NULL OR :at<unit.valid_until)
  AND management_grant.valid_from<=:at
  AND (management_grant.valid_until IS NULL OR :at<management_grant.valid_until)
  AND (management_grant.revoked_at IS NULL OR :at<management_grant.revoked_at)
  AND (management_grant.root_unit_id=unit.unit_id OR
       (management_grant.include_descendants AND EXISTS(
    SELECT 1 FROM organisation_unit_closure closure
    WHERE closure.ancestor_unit_id=management_grant.root_unit_id
      AND closure.descendant_unit_id=unit.unit_id)))
ORDER BY unit.unit_id,management_grant.grant_id LIMIT 101
"""

_ROSTER = """
SELECT member.unit_id,member.user_id,member.assignment_eligible,
       member.version AS membership_version,
       profile.wip_limit,
       account.is_active,account.roles,account.source_hash,
       (SELECT count(*) FROM team_memberships sole
        WHERE sole.user_id=member.user_id AND sole.state='active'
          AND sole.valid_from<=:start AND (sole.valid_until IS NULL OR :start<sole.valid_until)
       ) AS home_count,
       (SELECT count(*) FROM canonical_work_packages package
        WHERE package.accountable_user_id=member.user_id
          AND package.state IN ('pending','ready','in_progress','blocked')) AS active_wip
FROM team_memberships member
JOIN team_delivery_profiles profile ON profile.unit_id=member.unit_id AND profile.is_active
LEFT JOIN identity_account_projection account ON account.user_id=member.user_id
WHERE member.unit_id=ANY(CAST(:unit_ids AS uuid[])) AND member.state='active'
  AND member.valid_from<=:start AND (member.valid_until IS NULL OR :deadline<=member.valid_until)
ORDER BY member.unit_id,member.user_id LIMIT 501
"""

_TEAM_CAPABILITIES = """
SELECT profile.unit_id,count(DISTINCT coverage.capability_id)::integer AS matched
FROM team_delivery_profiles profile
JOIN team_capability_coverage coverage ON coverage.profile_id=profile.profile_id
WHERE profile.unit_id=ANY(CAST(:unit_ids AS uuid[])) AND profile.is_active
  AND coverage.capability_id=ANY(CAST(:capabilities AS text[]))
  AND coverage.valid_from<=:start
  AND (coverage.valid_until IS NULL OR :deadline<=coverage.valid_until)
GROUP BY profile.unit_id
"""

_PERSON_COMPETENCIES = """
SELECT user_id,count(DISTINCT capability_id)::integer AS matched
FROM assignment_competencies
WHERE user_id=ANY(CAST(:user_ids AS uuid[]))
  AND capability_id=ANY(CAST(:capabilities AS text[]))
  AND verified_at<=:start AND (expires_at IS NULL OR :deadline<=expires_at)
GROUP BY user_id
"""

_ACTIVE_HOLDS = """
SELECT coalesce(sum(held_minutes),0) FROM assignment_demand_holds
WHERE unit_id=:unit_id AND state='active' AND expires_at>:at
  AND (CAST(:exclude_id AS uuid) IS NULL OR recommendation_id<>CAST(:exclude_id AS uuid))
  AND starts_at<:deadline AND ends_at>:start
"""
