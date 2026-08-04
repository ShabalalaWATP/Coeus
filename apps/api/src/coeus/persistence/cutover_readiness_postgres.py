"""Bounded PostgreSQL evidence for organisation cutover readiness."""

from collections.abc import Mapping

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from coeus.domain.cutover_readiness import (
    CutoverCheckCode,
    CutoverCheckStatus,
    CutoverReadinessCheck,
)
from coeus.domain.jioc_principals import JIOC_AGENT_PRINCIPAL, JIOC_CAPACITY_GRANT_ID
from coeus.persistence.cutover_activation_snapshots import SCHEMA_HEAD

# Readiness and activation must agree on the schema they certify, so this reads
# the same constant rather than repeating the revision.
ALEMBIC_HEAD = SCHEMA_HEAD


class PostgresCutoverReadinessStore:
    """Inspect one repeatable-read snapshot without acquiring write locks."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def inspect(self) -> tuple[CutoverReadinessCheck, ...]:
        with (
            self._engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn,
            conn.begin(),
        ):
            conn.execute(text("SET LOCAL statement_timeout = '5s'"))
            values = _evidence(conn)
        return _checks(values)


def _scalar(
    connection: Connection, statement: str, parameters: Mapping[str, object] | None = None
) -> int:
    value = connection.execute(text(statement), parameters or {}).scalar_one()
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("cutover readiness query returned an invalid count")
    if value < 0:
        raise ValueError("cutover readiness query returned a negative count")
    return value


def _evidence(connection: Connection) -> dict[CutoverCheckCode, int]:
    parameters = {
        "head": ALEMBIC_HEAD,
        "grant_id": JIOC_CAPACITY_GRANT_ID,
        "principal_id": JIOC_AGENT_PRINCIPAL,
    }
    return {
        CutoverCheckCode.MIGRATION_HEAD: _scalar(connection, _MIGRATION, parameters),
        CutoverCheckCode.ORGANISATION_TOPOLOGY: _scalar(connection, _TOPOLOGY),
        CutoverCheckCode.IDENTITY_PROJECTION: _scalar(connection, _IDENTITY_PRESENT),
        CutoverCheckCode.IDENTITY_REFERENCE_PARITY: _scalar(connection, _IDENTITY_PARITY),
        CutoverCheckCode.BLOCKING_FINDINGS: _scalar(connection, _BLOCKING_FINDINGS),
        CutoverCheckCode.WORKFLOW_OWNERSHIP: _scalar(connection, _WORKFLOW_OWNERSHIP),
        CutoverCheckCode.PACKAGE_INTEGRITY: _scalar(connection, _PACKAGE_ORPHANS),
        CutoverCheckCode.RESERVATION_INTEGRITY: _scalar(connection, _RESERVATION_ORPHANS),
        CutoverCheckCode.ROUTING_LEAF_COVERAGE: _scalar(connection, _ROUTING_LEAVES),
        CutoverCheckCode.ROUTING_CAPABILITY_MAPPINGS: _scalar(connection, _ROUTING_MAPPINGS),
        CutoverCheckCode.JIOC_SERVICE_GRANT: _scalar(connection, _JIOC_GRANT, parameters),
    }


def _checks(values: Mapping[CutoverCheckCode, int]) -> tuple[CutoverReadinessCheck, ...]:
    exact = {
        CutoverCheckCode.MIGRATION_HEAD: 1,
        CutoverCheckCode.IDENTITY_PROJECTION: 1,
        CutoverCheckCode.ROUTING_LEAF_COVERAGE: 7,
        CutoverCheckCode.ROUTING_CAPABILITY_MAPPINGS: 40,
        CutoverCheckCode.JIOC_SERVICE_GRANT: 1,
    }
    checks = []
    for code in tuple(CutoverCheckCode)[:11]:
        value = values[code]
        required = exact.get(code, 0)
        passed = value == required
        checks.append(
            CutoverReadinessCheck(
                code,
                CutoverCheckStatus.PASSED if passed else CutoverCheckStatus.BLOCKED,
                value,
                required,
            )
        )
    return tuple(checks)


_MIGRATION = "SELECT COUNT(*)::integer FROM alembic_version WHERE version_num=:head"

_TOPOLOGY = """
WITH RECURSIVE expected(ancestor, descendant, depth) AS (
  SELECT unit_id, unit_id, 0 FROM organisation_units WHERE is_active
  UNION ALL
  SELECT expected.ancestor, child.unit_id, expected.depth + 1
  FROM expected JOIN organisation_units child ON child.parent_unit_id=expected.descendant
  WHERE child.is_active AND expected.depth < 12
), differences AS (
  (SELECT ancestor,descendant,depth FROM expected
   EXCEPT SELECT ancestor_unit_id,descendant_unit_id,depth
          FROM organisation_unit_closure)
  UNION ALL
  (SELECT ancestor_unit_id,descendant_unit_id,depth
   FROM organisation_unit_closure
   WHERE ancestor_unit_id IN (SELECT unit_id FROM organisation_units WHERE is_active)
     AND descendant_unit_id IN (SELECT unit_id FROM organisation_units WHERE is_active)
   EXCEPT SELECT ancestor,descendant,depth FROM expected)
), root_error AS (
  SELECT CASE WHEN COUNT(*)=1 THEN 0 ELSE 1 END AS value
  FROM organisation_units WHERE is_active AND parent_unit_id IS NULL
)
SELECT ((SELECT COUNT(*) FROM differences)+(SELECT value FROM root_error))::integer
"""

_IDENTITY_PRESENT = "SELECT LEAST(COUNT(*),1)::integer FROM identity_account_projection"

_IDENTITY_PARITY = """
WITH referenced(user_id) AS (
  SELECT user_id FROM team_memberships WHERE state='active'
  UNION SELECT accountable_user_id FROM canonical_work_packages
        WHERE accountable_user_id IS NOT NULL AND state NOT IN ('complete','cancelled')
  UNION SELECT user_id FROM capacity_reservations WHERE state IN ('held','active')
)
SELECT COUNT(*)::integer FROM referenced
LEFT JOIN identity_account_projection account USING (user_id)
WHERE account.user_id IS NULL OR NOT account.is_active
"""

_BLOCKING_FINDINGS = """
SELECT (
  (SELECT COUNT(*) FROM organisation_reconciliation_findings
   WHERE severity='blocking' AND resolved_at IS NULL) +
  (SELECT COUNT(*) FROM team_task_ownership WHERE state='ownership_unresolved')
)::integer
"""

_WORKFLOW_OWNERSHIP = """
SELECT COUNT(*)::integer
FROM coeus_ticket_aggregates ticket
WHERE ticket.consumes_capacity
  AND ticket.state IN ('ANALYST_ASSIGNMENT','ANALYST_IN_PROGRESS','MANAGER_APPROVAL',
    'QC_REVIEW','REWORK_REQUIRED','DISSEMINATION_READY','MANAGER_REANALYSIS_REVIEW',
    'JIOC_REANALYSIS_ADJUDICATION')
  AND NOT EXISTS (
    SELECT 1 FROM team_task_ownership ownership
    WHERE ownership.ticket_id=ticket.ticket_id
      AND ownership.state NOT IN ('cancelled','ownership_unresolved')
  )
"""

_PACKAGE_ORPHANS = """
SELECT COUNT(*)::integer FROM canonical_work_packages package
LEFT JOIN organisation_units unit ON unit.unit_id=package.owning_unit_id AND unit.is_active
LEFT JOIN coeus_ticket_aggregates ticket ON ticket.ticket_id=package.ticket_id
LEFT JOIN team_task_ownership ownership ON ownership.ticket_id=package.ticket_id
  AND ownership.workflow_leg=package.workflow_leg
LEFT JOIN identity_account_projection account ON account.user_id=package.accountable_user_id
WHERE unit.unit_id IS NULL OR ticket.ticket_id IS NULL OR ownership.ownership_id IS NULL OR (
  package.accountable_user_id IS NOT NULL
  AND (account.user_id IS NULL OR NOT account.is_active)
)
"""

_RESERVATION_ORPHANS = """
SELECT COUNT(*)::integer FROM capacity_reservations reservation
LEFT JOIN canonical_work_packages package ON package.package_id=reservation.package_id
  AND package.ticket_id=reservation.ticket_id AND package.workflow_leg=reservation.workflow_leg
LEFT JOIN identity_account_projection account ON account.user_id=reservation.user_id
WHERE reservation.state IN ('held','active') AND (
  package.package_id IS NULL OR package.state IN ('complete','cancelled')
  OR account.user_id IS NULL OR NOT account.is_active
)
"""

_ROUTING_LEAVES = """
SELECT COUNT(DISTINCT profile.unit_id)::integer
FROM team_capability_coverage coverage
JOIN team_delivery_profiles profile ON profile.profile_id=coverage.profile_id
JOIN organisation_units unit ON unit.unit_id=profile.unit_id
WHERE coverage.capability_id ~ '^(RFA-|CM-)' AND coverage.valid_until IS NULL
  AND profile.is_active AND unit.is_active
"""

_ROUTING_MAPPINGS = """
SELECT COUNT(DISTINCT coverage.capability_id)::integer
FROM team_capability_coverage coverage
JOIN team_delivery_profiles profile ON profile.profile_id=coverage.profile_id
JOIN organisation_units unit ON unit.unit_id=profile.unit_id
WHERE coverage.capability_id ~ '^(RFA-|CM-)' AND coverage.valid_until IS NULL
  AND profile.is_active AND unit.is_active
"""

_JIOC_GRANT = """
SELECT COUNT(*)::integer FROM (
  SELECT grant_row.grant_id FROM team_management_grants grant_row
  JOIN identity_account_projection creator
    ON creator.user_id=grant_row.created_by_user_id AND creator.is_active
  JOIN organisation_unit_closure closure ON closure.ancestor_unit_id=grant_row.root_unit_id
  JOIN team_delivery_profiles profile ON profile.unit_id=closure.descendant_unit_id
  WHERE grant_row.grant_id=:grant_id AND grant_row.manager_user_id=:principal_id
    AND grant_row.action='recommendation:view' AND grant_row.include_descendants
    AND grant_row.source_grant_id IS NULL AND grant_row.delegation_depth=0
    AND grant_row.revoked_at IS NULL AND grant_row.valid_from<=CURRENT_TIMESTAMP
    AND (grant_row.valid_until IS NULL OR CURRENT_TIMESTAMP<grant_row.valid_until)
  GROUP BY grant_row.grant_id
  HAVING COUNT(DISTINCT profile.unit_id) FILTER (WHERE profile.is_active)=7
) eligible
"""
