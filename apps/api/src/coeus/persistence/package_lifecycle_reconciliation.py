"""Repeatable reconciliation for time-driven package lifecycle changes."""

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Engine


@dataclass(frozen=True)
class PackageLifecycleReconciliationResult:
    ineligible_people: int
    competency_conflicts: int
    capability_conflicts: int


def reconcile_due_package_lifecycle(engine: Engine) -> PackageLifecycleReconciliationResult:
    """Apply monotonic eligibility loss and create reviewable planning conflicts."""
    with engine.begin() as connection:
        connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
            {"key": "package-lifecycle-due-reconciliation-v1"},
        )
        people = tuple(connection.execute(text(_INELIGIBLE_PEOPLE)).mappings())
        for row in people:
            connection.execute(
                text("SELECT reconcile_ineligible_participant(:user_id,:reason,:source)"),
                dict(row),
            )
        competency = int(connection.execute(text(_COMPETENCY_CONFLICTS)).scalar_one())
        capability = int(connection.execute(text(_CAPABILITY_CONFLICTS)).scalar_one())
        connection.execute(text(_HOLD_REVIEW_CAPACITY))
        return PackageLifecycleReconciliationResult(len(people), competency, capability)


_INELIGIBLE_PEOPLE = """
SELECT DISTINCT participant.user_id,
  CASE
    WHEN account.user_id IS NULL OR NOT account.is_active OR NOT ('Analyst'=ANY(account.roles))
      THEN 'account_ineligible'
    WHEN NOT unit.is_active THEN 'team_inactive'
    ELSE 'membership_ineligible'
  END reason,
  COALESCE(membership.membership_id::text,participant.user_id::text) source
FROM work_package_participants participant
JOIN canonical_work_packages package ON package.package_id=participant.package_id
LEFT JOIN identity_account_projection account ON account.user_id=participant.user_id
LEFT JOIN team_memberships membership ON membership.user_id=participant.user_id
  AND membership.unit_id=package.owning_unit_id AND membership.state='active'
  AND membership.assignment_eligible AND membership.valid_from<=now()
  AND (membership.valid_until IS NULL OR now()<membership.valid_until)
JOIN organisation_units unit ON unit.unit_id=package.owning_unit_id
WHERE participant.active AND package.state NOT IN ('complete','cancelled')
  AND (account.user_id IS NULL OR NOT account.is_active OR NOT ('Analyst'=ANY(account.roles))
       OR membership.membership_id IS NULL OR NOT unit.is_active)
ORDER BY participant.user_id
"""

_COMPETENCY_CONFLICTS = """
WITH inserted AS (
 INSERT INTO package_lifecycle_conflicts
  (conflict_id,package_id,reason_code,source_type,source_id,evidence,observed_at)
 SELECT gen_random_uuid(),participant.package_id,'competency_review_required','competency',
        competency.competency_id::text,'{}'::jsonb,now()
 FROM assignment_competencies competency
 JOIN work_package_participants participant ON participant.user_id=competency.user_id
 JOIN canonical_work_packages package ON package.package_id=participant.package_id
 WHERE competency.expires_at<=now() AND participant.active
   AND package.state NOT IN ('complete','cancelled')
 ON CONFLICT (package_id,reason_code,source_type,source_id) WHERE status='open' DO NOTHING
 RETURNING 1
) SELECT count(*) FROM inserted
"""

_CAPABILITY_CONFLICTS = """
WITH inserted AS (
 INSERT INTO package_lifecycle_conflicts
  (conflict_id,package_id,reason_code,source_type,source_id,evidence,observed_at)
 SELECT gen_random_uuid(),package.package_id,'capability_review_required','capability',
        coverage.coverage_id::text,'{}'::jsonb,now()
 FROM team_capability_coverage coverage
 JOIN team_delivery_profiles profile ON profile.profile_id=coverage.profile_id
 JOIN canonical_work_packages package ON package.owning_unit_id=profile.unit_id
 WHERE coverage.valid_until<=now() AND package.state NOT IN ('complete','cancelled')
 ON CONFLICT (package_id,reason_code,source_type,source_id) WHERE status='open' DO NOTHING
 RETURNING 1
) SELECT count(*) FROM inserted
"""

_HOLD_REVIEW_CAPACITY = """
UPDATE capacity_reservations reservation SET state='held',version=version+1,updated_at=now()
WHERE state='active' AND ends_at>now() AND EXISTS (
 SELECT 1 FROM package_lifecycle_conflicts conflict
 WHERE conflict.package_id=reservation.package_id AND conflict.status='open'
   AND conflict.reason_code IN ('competency_review_required','capability_review_required')
)
"""
