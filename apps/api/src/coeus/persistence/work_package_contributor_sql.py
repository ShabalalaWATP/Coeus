"""SQL for reviewed contributor lifecycle commands."""

PACKAGE = """
SELECT package.*,ownership.version ownership_version,
       ownership.state ownership_state,ownership.owning_unit_id ownership_unit_id
FROM canonical_work_packages package
JOIN team_task_ownership ownership
  ON ownership.ticket_id=package.ticket_id
 AND ownership.workflow_leg=package.workflow_leg
WHERE package.package_id=:package_id
"""
PACKAGE_FOR_UPDATE = PACKAGE + " FOR UPDATE OF package,ownership"

LEAF_UNIT = """
SELECT unit.unit_id FROM organisation_units unit
WHERE unit.unit_id=:unit_id AND unit.is_active
  AND unit.valid_from<=:at AND (unit.valid_until IS NULL OR :at<unit.valid_until)
  AND NOT EXISTS (
    SELECT 1 FROM organisation_units child
    WHERE child.parent_unit_id=unit.unit_id AND child.is_active
      AND child.valid_from<=:at AND (child.valid_until IS NULL OR :at<child.valid_until)
  )
FOR UPDATE
"""

GRANT = """
SELECT grant_id,root_unit_id,version
FROM team_management_grants
WHERE grant_id=:grant_id AND manager_user_id=:actor_id AND action='task:assign'
  AND valid_from<=:at AND (valid_until IS NULL OR :at<valid_until)
  AND (revoked_at IS NULL OR :at<revoked_at)
  AND (root_unit_id=:unit_id OR (
    include_descendants AND EXISTS(
      SELECT 1 FROM organisation_unit_closure
      WHERE ancestor_unit_id=root_unit_id AND descendant_unit_id=:unit_id
    )
  ))
FOR UPDATE
"""

ACCOUNT = """
SELECT user_id,is_active,roles,credential_version,source_hash
FROM identity_account_projection WHERE user_id=:user_id FOR UPDATE
"""

MEMBERSHIPS = """
SELECT membership_id,unit_id,assignment_eligible,version
FROM team_memberships
WHERE user_id=:user_id AND state='active'
  AND assignment_eligible AND valid_from<=:at
  AND (valid_until IS NULL OR :at<valid_until)
FOR UPDATE
"""

PARTICIPANT = """
SELECT active FROM work_package_participants
WHERE package_id=:package_id AND user_id=:user_id AND role='contributor'
FOR UPDATE
"""

UPDATE_PACKAGE = """
UPDATE canonical_work_packages SET version=version+1,updated_at=:at
WHERE package_id=:package_id AND version=:expected_version RETURNING version
"""

ADD_PARTICIPANT = """
INSERT INTO work_package_participants(package_id,user_id,role,active,created_at,ended_at)
VALUES (:package_id,:user_id,'contributor',true,:at,NULL)
ON CONFLICT (package_id,user_id,role)
DO UPDATE SET active=true,created_at=EXCLUDED.created_at,ended_at=NULL
"""

END_PARTICIPANT = """
UPDATE work_package_participants SET active=false,ended_at=:at
WHERE package_id=:package_id AND user_id=:user_id AND role='contributor' AND active
"""

COMMANDS = """
SELECT * FROM work_package_contributor_commands
WHERE command_id=:command_id OR idempotency_key=:idempotency_key
ORDER BY command_id FOR UPDATE
"""

INSERT_COMMAND = """
INSERT INTO work_package_contributor_commands(
 command_id,idempotency_key,request_hash,package_id,contributor_user_id,actor_user_id,
 operation,expected_package_version,result_package_version,result_active,occurred_at)
VALUES (
 :command_id,:idempotency_key,:request_hash,:package_id,:contributor_user_id,:actor_user_id,
 :operation,:expected_package_version,:result_package_version,:result_active,:occurred_at)
"""

INSERT_HISTORY = """
INSERT INTO work_package_history(
 history_id,package_id,version,actor_user_id,event_type,evidence,occurred_at)
VALUES (
 :history_id,:package_id,:version,:actor_user_id,:event_type,
 CAST(:evidence AS jsonb),:occurred_at)
"""
