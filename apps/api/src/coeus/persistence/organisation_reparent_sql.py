"""SQL used by transactional organisation reparent commands."""

LOAD_COMMAND = """
SELECT * FROM organisation_reparent_commands
WHERE command_id=:command_id OR idempotency_key=:idempotency_key
ORDER BY command_id
"""

LOCK_UNITS = """
SELECT unit_id FROM organisation_units
WHERE unit_id IN (
  SELECT descendant_unit_id FROM organisation_unit_closure WHERE ancestor_unit_id=:unit_id
  UNION SELECT :new_parent_unit_id
) ORDER BY unit_id FOR UPDATE
"""

IMPACT = """
WITH subtree AS (
  SELECT descendant_unit_id,depth FROM organisation_unit_closure
  WHERE ancestor_unit_id=:unit_id
), old_ancestors AS (
  SELECT ancestor_unit_id FROM organisation_unit_closure
  WHERE descendant_unit_id=:unit_id
), new_ancestors AS (
  SELECT ancestor_unit_id FROM organisation_unit_closure
  WHERE descendant_unit_id=:new_parent_unit_id
), relevant_grants AS (
  SELECT DISTINCT grant_id FROM team_management_grants
  WHERE root_unit_id IN (
    SELECT descendant_unit_id FROM subtree UNION SELECT ancestor_unit_id FROM old_ancestors
    UNION SELECT ancestor_unit_id FROM new_ancestors
  )
), new_grants AS (
  SELECT grant_id FROM team_management_grants grant_row
  WHERE grant_row.include_descendants AND grant_row.revoked_at IS NULL
    AND (grant_row.valid_until IS NULL OR grant_row.valid_until > transaction_timestamp())
    AND grant_row.root_unit_id IN (SELECT ancestor_unit_id FROM new_ancestors)
    AND NOT EXISTS (
      SELECT 1 FROM organisation_unit_closure current_scope
      WHERE current_scope.ancestor_unit_id=grant_row.root_unit_id
        AND current_scope.descendant_unit_id=:unit_id
    )
)
SELECT unit_row.parent_unit_id,
  (SELECT revision_id FROM organisation_topology_revisions
   WHERE unit_id=:unit_id ORDER BY valid_from DESC,revision_id DESC LIMIT 1) revision_id,
  GREATEST((SELECT count(*) - 1 FROM subtree),0) descendants,
  (SELECT count(*) FROM team_memberships WHERE unit_id IN
    (SELECT descendant_unit_id FROM subtree) AND state <> 'cancelled') memberships,
  (SELECT count(*) FROM relevant_grants) grants,
  (SELECT count(*) FROM team_capability_coverage coverage JOIN team_delivery_profiles profile
    ON profile.profile_id=coverage.profile_id WHERE profile.unit_id IN
    (SELECT descendant_unit_id FROM subtree)) capability_mappings,
  (SELECT count(*) FROM team_task_ownership WHERE owning_unit_id IN
    (SELECT descendant_unit_id FROM subtree)
    AND state NOT IN ('completed','cancelled')) active_task_legs,
  (SELECT count(*) FROM new_grants) newly_covering_grants,
  (SELECT COALESCE(max(depth),0) FROM organisation_unit_closure
    WHERE descendant_unit_id=:new_parent_unit_id) + 1 +
  (SELECT COALESCE(max(depth),0) FROM subtree) maximum_result_depth,
  (SELECT string_agg(descendant_unit_id::text || ':' || depth::text,','
    ORDER BY depth,descendant_unit_id) FROM subtree) subtree_state,
  (SELECT string_agg(grant_row.grant_id::text || ':' || grant_row.version::text || ':' ||
    grant_row.root_unit_id::text || ':' || grant_row.include_descendants::text || ':' ||
    COALESCE(grant_row.revoked_at::text,''),',' ORDER BY grant_row.grant_id)
    FROM team_management_grants grant_row JOIN relevant_grants relevant
    ON relevant.grant_id=grant_row.grant_id) grant_state,
  (SELECT string_agg(membership_id::text || ':' || version::text || ':' || unit_id::text || ':' ||
    state || ':' || valid_from::text || ':' || COALESCE(valid_until::text,''),','
    ORDER BY membership_id)
    FROM team_memberships WHERE unit_id IN
    (SELECT descendant_unit_id FROM subtree) AND state <> 'cancelled') membership_state,
  (SELECT string_agg(coverage.coverage_id::text || ':' || coverage.policy_version::text,','
    ORDER BY coverage.coverage_id) FROM team_capability_coverage coverage
    JOIN team_delivery_profiles profile ON profile.profile_id=coverage.profile_id
    WHERE profile.unit_id IN (SELECT descendant_unit_id FROM subtree)) capability_state,
  (SELECT string_agg(ownership_id::text || ':' || version::text,',' ORDER BY ownership_id)
    FROM team_task_ownership WHERE owning_unit_id IN
    (SELECT descendant_unit_id FROM subtree) AND state NOT IN ('completed','cancelled')) task_state,
  unit_row.version source_version,parent_row.version parent_version,
  unit_row.is_active source_active,parent_row.is_active parent_active
FROM organisation_units unit_row
JOIN organisation_units parent_row ON parent_row.unit_id=:new_parent_unit_id
WHERE unit_row.unit_id=:unit_id
"""

UPDATE_PARENT = """
UPDATE organisation_units SET parent_unit_id=:new_parent_unit_id,version=version + 1,
 updated_at=:occurred_at WHERE unit_id=:unit_id AND version=:expected_unit_version AND is_active
RETURNING version
"""

DELETE_EXTERNAL_CLOSURE = """
DELETE FROM organisation_unit_closure
WHERE descendant_unit_id IN (
  SELECT descendant_unit_id FROM organisation_unit_closure WHERE ancestor_unit_id=:unit_id
) AND ancestor_unit_id NOT IN (
  SELECT descendant_unit_id FROM organisation_unit_closure WHERE ancestor_unit_id=:unit_id
)
"""

INSERT_EXTERNAL_CLOSURE = """
INSERT INTO organisation_unit_closure(ancestor_unit_id,descendant_unit_id,depth)
SELECT parent_path.ancestor_unit_id,subtree.descendant_unit_id,
 parent_path.depth + 1 + subtree.depth
FROM organisation_unit_closure parent_path
CROSS JOIN organisation_unit_closure subtree
WHERE parent_path.descendant_unit_id=:new_parent_unit_id
  AND subtree.ancestor_unit_id=:unit_id
"""

LOAD_REVISION_PATHS = """
SELECT unit_row.unit_id,unit_row.parent_unit_id,
 array_agg(closure.ancestor_unit_id ORDER BY closure.depth DESC) path
FROM organisation_units unit_row
JOIN organisation_unit_closure closure ON closure.descendant_unit_id=unit_row.unit_id
WHERE unit_row.unit_id IN (
  SELECT descendant_unit_id FROM organisation_unit_closure WHERE ancestor_unit_id=:unit_id
)
GROUP BY unit_row.unit_id,unit_row.parent_unit_id
ORDER BY unit_row.unit_id
"""

INSERT_REVISION = """
INSERT INTO organisation_topology_revisions(revision_id,unit_id,parent_unit_id,path,
 valid_from,valid_until,change_command_id,changed_by_user_id)
VALUES (:revision_id,:revision_unit_id,:revision_parent_unit_id,:path,
 :occurred_at,NULL,:command_id,:actor_user_id)
RETURNING revision_id
"""

INSERT_COMMAND = """
INSERT INTO organisation_reparent_commands(command_id,idempotency_key,request_hash,
 reason_hash,actor_user_id,unit_id,source_parent_unit_id,new_parent_unit_id,authorising_grant_id,
 expected_unit_version,expected_parent_version,result_version,topology_revision_id,occurred_at)
VALUES (:command_id,:idempotency_key,:request_hash,:reason_hash,:actor_user_id,:unit_id,
 :source_parent_unit_id,:new_parent_unit_id,:authorising_grant_id,:expected_unit_version,
 :expected_parent_version,:result_version,:topology_revision_id,:occurred_at)
RETURNING command_id
"""
