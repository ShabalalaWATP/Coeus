"""SQL for fail-closed organisation unit deactivation."""

LOAD_COMMAND = """
SELECT * FROM organisation_deactivation_commands
WHERE command_id=:command_id OR idempotency_key=:idempotency_key
ORDER BY command_id
"""

IMPACT = """
WITH subtree AS (
 SELECT descendant_unit_id FROM organisation_unit_closure WHERE ancestor_unit_id=:unit_id
)
SELECT unit_row.version,unit_row.is_active,unit_row.parent_unit_id,
 (SELECT count(*) FROM organisation_units WHERE parent_unit_id=:unit_id AND is_active)
   active_children,
 (SELECT count(*) FROM organisation_units WHERE unit_id IN
   (SELECT descendant_unit_id FROM subtree) AND unit_id<>:unit_id AND is_active)
   active_descendants,
 (SELECT count(*) FROM team_memberships WHERE unit_id IN
   (SELECT descendant_unit_id FROM subtree) AND state<>'cancelled'
   AND (valid_until IS NULL OR valid_until>transaction_timestamp())) memberships,
 (SELECT count(*) FROM team_management_grants WHERE root_unit_id IN
   (SELECT descendant_unit_id FROM subtree) AND revoked_at IS NULL
   AND (valid_until IS NULL OR valid_until>transaction_timestamp())) direct_grants,
 (SELECT count(*) FROM team_delivery_profiles WHERE unit_id IN
   (SELECT descendant_unit_id FROM subtree) AND is_active) delivery_profiles,
 (SELECT count(*) FROM team_capability_coverage coverage JOIN team_delivery_profiles profile
   ON profile.profile_id=coverage.profile_id WHERE profile.unit_id IN
   (SELECT descendant_unit_id FROM subtree)
   AND (coverage.valid_until IS NULL OR coverage.valid_until>transaction_timestamp()))
   capability_mappings,
 (SELECT count(*) FROM team_task_ownership WHERE owning_unit_id IN
   (SELECT descendant_unit_id FROM subtree) AND state NOT IN ('completed','cancelled'))
   active_task_legs,
 (SELECT count(*) FROM organisation_personnel_transfers WHERE status='pending'
   AND (source_unit_id IN (SELECT descendant_unit_id FROM subtree)
     OR target_unit_id IN (SELECT descendant_unit_id FROM subtree))) pending_transfers,
 COALESCE((SELECT string_agg(descendant_unit_id::text,',' ORDER BY descendant_unit_id)
   FROM subtree),'') subtree_state,
 COALESCE((SELECT string_agg(membership_id::text || ':' || version::text,','
   ORDER BY membership_id) FROM team_memberships WHERE unit_id IN
   (SELECT descendant_unit_id FROM subtree) AND state<>'cancelled'
   AND (valid_until IS NULL OR valid_until>transaction_timestamp())),'') membership_state,
 COALESCE((SELECT string_agg(grant_id::text || ':' || version::text,',' ORDER BY grant_id)
   FROM team_management_grants WHERE root_unit_id IN
   (SELECT descendant_unit_id FROM subtree) AND revoked_at IS NULL),'') grant_state
FROM organisation_units unit_row WHERE unit_row.unit_id=:unit_id
"""

DEACTIVATE = """
UPDATE organisation_units SET is_active=false,valid_until=:occurred_at,
 version=version + 1,updated_at=:occurred_at
WHERE unit_id=:unit_id AND version=:expected_version AND is_active
RETURNING version
"""

INSERT_COMMAND = """
INSERT INTO organisation_deactivation_commands(command_id,idempotency_key,request_hash,
 reason_hash,actor_user_id,unit_id,authorising_grant_id,expected_version,result_version,
 occurred_at)
VALUES (:command_id,:idempotency_key,:request_hash,:reason_hash,:actor_user_id,:unit_id,
 :authorising_grant_id,:expected_version,:result_version,:occurred_at)
RETURNING command_id
"""
