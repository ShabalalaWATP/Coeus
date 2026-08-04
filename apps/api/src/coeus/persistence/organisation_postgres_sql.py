"""Write statements for organisation shadow reconciliation."""

UPSERT_UNIT = """
INSERT INTO organisation_units(unit_id, name, short_name, category, parent_unit_id, is_active,
 valid_from, valid_until, time_zone, description, version, provenance)
VALUES (:unit_id, :name, :short_name, :category, :parent_unit_id, :is_active,
 :valid_from, :valid_until, :time_zone, :description, :version, :provenance)
ON CONFLICT (unit_id) DO UPDATE SET name = EXCLUDED.name, short_name = EXCLUDED.short_name,
 category = EXCLUDED.category, is_active = EXCLUDED.is_active, valid_from = EXCLUDED.valid_from,
 valid_until = EXCLUDED.valid_until, time_zone = EXCLUDED.time_zone,
 description = EXCLUDED.description, provenance = EXCLUDED.provenance,
 version = EXCLUDED.version, updated_at = now()
 WHERE organisation_units.parent_unit_id IS NOT DISTINCT FROM EXCLUDED.parent_unit_id
 AND organisation_units.provenance = EXCLUDED.provenance AND (
  EXCLUDED.version > organisation_units.version OR (
   EXCLUDED.version = organisation_units.version AND
   organisation_units.name = EXCLUDED.name AND
   organisation_units.short_name = EXCLUDED.short_name AND
   organisation_units.category = EXCLUDED.category AND
   organisation_units.is_active = EXCLUDED.is_active AND
   organisation_units.valid_from = EXCLUDED.valid_from AND
   organisation_units.valid_until IS NOT DISTINCT FROM EXCLUDED.valid_until AND
   organisation_units.time_zone = EXCLUDED.time_zone AND
   organisation_units.description = EXCLUDED.description AND
   organisation_units.provenance = EXCLUDED.provenance))
RETURNING unit_id
"""

INSERT_REVISION = """
INSERT INTO organisation_topology_revisions(revision_id, unit_id, parent_unit_id, path,
 valid_from, valid_until, change_command_id, changed_by_user_id)
VALUES (:revision_id, :unit_id, :parent_unit_id, :path, :valid_from, :valid_until,
 :change_command_id, :changed_by_user_id)
 ON CONFLICT (revision_id) DO NOTHING RETURNING revision_id
"""

UPSERT_MEMBERSHIP = """
INSERT INTO team_memberships(membership_id, user_id, unit_id, role, state, assignment_eligible,
 valid_from, valid_until, created_by_user_id, reason, provenance, version)
VALUES (:membership_id, :user_id, :unit_id, :role, :state, :assignment_eligible, :valid_from,
 :valid_until, :created_by_user_id, :reason, :provenance, :version)
ON CONFLICT (membership_id) DO UPDATE SET role=EXCLUDED.role, state=EXCLUDED.state,
 assignment_eligible=EXCLUDED.assignment_eligible, valid_from=EXCLUDED.valid_from,
 valid_until=EXCLUDED.valid_until, reason=EXCLUDED.reason, provenance=EXCLUDED.provenance,
 version=EXCLUDED.version, updated_at=now()
 WHERE team_memberships.user_id=EXCLUDED.user_id AND team_memberships.unit_id=EXCLUDED.unit_id
 AND NOT (team_memberships.state IN ('ended', 'cancelled')
          AND EXCLUDED.state <> team_memberships.state)
 AND (EXCLUDED.version > team_memberships.version OR (
  EXCLUDED.version = team_memberships.version AND team_memberships.role = EXCLUDED.role
  AND team_memberships.state = EXCLUDED.state
  AND team_memberships.assignment_eligible = EXCLUDED.assignment_eligible
  AND team_memberships.valid_from = EXCLUDED.valid_from
  AND team_memberships.valid_until IS NOT DISTINCT FROM EXCLUDED.valid_until
  AND team_memberships.created_by_user_id = EXCLUDED.created_by_user_id
  AND team_memberships.reason = EXCLUDED.reason
  AND team_memberships.provenance = EXCLUDED.provenance))
RETURNING membership_id
"""

UPSERT_GRANT = """
INSERT INTO team_management_grants(grant_id, manager_user_id, root_unit_id, action,
 include_descendants, valid_from, valid_until, revoked_at, created_by_user_id, reason,
 source_grant_id, delegation_depth, version) VALUES (
 :grant_id, :manager_user_id, :root_unit_id, :action,
 :include_descendants, :valid_from, :valid_until, :revoked_at, :created_by_user_id, :reason,
 :source_grant_id, :delegation_depth, :version) ON CONFLICT (grant_id) DO UPDATE SET
 include_descendants=EXCLUDED.include_descendants, valid_from=EXCLUDED.valid_from,
 valid_until=EXCLUDED.valid_until, revoked_at=EXCLUDED.revoked_at, reason=EXCLUDED.reason,
 source_grant_id=EXCLUDED.source_grant_id, delegation_depth=EXCLUDED.delegation_depth,
 version=EXCLUDED.version, updated_at=now()
 WHERE team_management_grants.manager_user_id=EXCLUDED.manager_user_id
 AND team_management_grants.root_unit_id=EXCLUDED.root_unit_id
 AND team_management_grants.action=EXCLUDED.action
 AND (team_management_grants.revoked_at IS NULL
      OR team_management_grants.revoked_at = EXCLUDED.revoked_at)
 AND (EXCLUDED.version > team_management_grants.version OR (
  EXCLUDED.version = team_management_grants.version
  AND team_management_grants.include_descendants = EXCLUDED.include_descendants
  AND team_management_grants.valid_from = EXCLUDED.valid_from
  AND team_management_grants.valid_until IS NOT DISTINCT FROM EXCLUDED.valid_until
  AND team_management_grants.revoked_at IS NOT DISTINCT FROM EXCLUDED.revoked_at
  AND team_management_grants.created_by_user_id = EXCLUDED.created_by_user_id
  AND team_management_grants.reason = EXCLUDED.reason
  AND team_management_grants.source_grant_id IS NOT DISTINCT FROM EXCLUDED.source_grant_id
  AND team_management_grants.delegation_depth = EXCLUDED.delegation_depth))
 RETURNING grant_id
"""

UPSERT_PROFILE = """
INSERT INTO team_delivery_profiles(profile_id, unit_id, route, wip_limit, weekly_hours,
 policy_version, is_active, provenance) VALUES (:profile_id, :unit_id, :route, :wip_limit,
 :weekly_hours, :policy_version, :is_active, :provenance)
 ON CONFLICT (profile_id) DO UPDATE SET route=EXCLUDED.route,
 wip_limit=EXCLUDED.wip_limit, weekly_hours=EXCLUDED.weekly_hours,
 policy_version=EXCLUDED.policy_version,
 is_active=EXCLUDED.is_active, provenance=EXCLUDED.provenance, updated_at=now()
 WHERE team_delivery_profiles.unit_id=EXCLUDED.unit_id
 AND team_delivery_profiles.provenance=EXCLUDED.provenance AND (
  EXCLUDED.policy_version > team_delivery_profiles.policy_version OR (
   EXCLUDED.policy_version = team_delivery_profiles.policy_version
   AND team_delivery_profiles.route = EXCLUDED.route
   AND team_delivery_profiles.wip_limit = EXCLUDED.wip_limit
   AND team_delivery_profiles.weekly_hours = EXCLUDED.weekly_hours
   AND team_delivery_profiles.is_active = EXCLUDED.is_active
   AND team_delivery_profiles.provenance = EXCLUDED.provenance))
 RETURNING profile_id
"""

UPSERT_COVERAGE = """
INSERT INTO team_capability_coverage(coverage_id, profile_id, capability_id, proficiency,
 valid_from, valid_until, policy_version, approved_by_user_id) VALUES (:coverage_id, :profile_id,
 :capability_id, :proficiency, :valid_from, :valid_until, :policy_version, :approved_by_user_id)
ON CONFLICT (coverage_id) DO UPDATE SET proficiency=EXCLUDED.proficiency,
 valid_from=EXCLUDED.valid_from, valid_until=EXCLUDED.valid_until,
 policy_version=EXCLUDED.policy_version,
 approved_by_user_id=EXCLUDED.approved_by_user_id
 WHERE team_capability_coverage.profile_id=EXCLUDED.profile_id
 AND team_capability_coverage.capability_id=EXCLUDED.capability_id AND (
  EXCLUDED.policy_version > team_capability_coverage.policy_version OR (
   EXCLUDED.policy_version = team_capability_coverage.policy_version
   AND team_capability_coverage.proficiency = EXCLUDED.proficiency
   AND team_capability_coverage.valid_from = EXCLUDED.valid_from
   AND team_capability_coverage.valid_until IS NOT DISTINCT FROM EXCLUDED.valid_until
   AND team_capability_coverage.approved_by_user_id = EXCLUDED.approved_by_user_id))
 RETURNING coverage_id
"""

UPSERT_EPOCH = """
INSERT INTO effective_authority_epochs(principal_id, scope_unit_id, epoch, advanced_at)
VALUES (:principal_id, :scope_unit_id, :epoch, :advanced_at)
ON CONFLICT (principal_id, scope_unit_id) DO UPDATE SET
 epoch=GREATEST(effective_authority_epochs.epoch, EXCLUDED.epoch),
 advanced_at=CASE WHEN EXCLUDED.epoch > effective_authority_epochs.epoch
 THEN EXCLUDED.advanced_at ELSE effective_authority_epochs.advanced_at END
RETURNING principal_id
"""

UPSERT_CHECKPOINT = """
INSERT INTO organisation_reconciliation_checkpoints(checkpoint_id, source_namespace,
 source_digest, status, cursor, started_at, completed_at) VALUES (:checkpoint_id,
 :source_namespace, :source_digest, :status, CAST(:cursor AS jsonb), :started_at, :completed_at)
ON CONFLICT (checkpoint_id) DO UPDATE SET status=EXCLUDED.status, cursor=EXCLUDED.cursor,
 completed_at=EXCLUDED.completed_at, updated_at=now()
WHERE organisation_reconciliation_checkpoints.source_namespace=EXCLUDED.source_namespace
 AND organisation_reconciliation_checkpoints.source_digest=EXCLUDED.source_digest
RETURNING checkpoint_id
"""

UPSERT_FINDING = """
INSERT INTO organisation_reconciliation_findings(finding_id, checkpoint_id, finding_code,
 severity, source_identifier, details, created_at, resolved_at, disposition)
VALUES (:finding_id, :checkpoint_id, :finding_code, :severity, :source_identifier,
 CAST(:details AS jsonb), :created_at, :resolved_at, :disposition)
ON CONFLICT (finding_id) DO UPDATE SET severity=EXCLUDED.severity, details=EXCLUDED.details,
 resolved_at=EXCLUDED.resolved_at, disposition=EXCLUDED.disposition
WHERE organisation_reconciliation_findings.checkpoint_id=EXCLUDED.checkpoint_id
 AND organisation_reconciliation_findings.finding_code=EXCLUDED.finding_code
 AND organisation_reconciliation_findings.source_identifier=EXCLUDED.source_identifier
RETURNING finding_id
"""
