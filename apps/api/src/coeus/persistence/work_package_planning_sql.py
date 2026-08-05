"""SQL for the atomic package plan-and-reserve command."""

PACKAGE = """
SELECT package.*, ownership.version AS ownership_version,
       ownership.state AS ownership_state,
       ownership.owning_unit_id AS ownership_unit_id
FROM canonical_work_packages package
JOIN team_task_ownership ownership
  ON ownership.ticket_id=package.ticket_id
 AND ownership.workflow_leg=package.workflow_leg
WHERE package.package_id=:package_id
"""

PACKAGE_FOR_UPDATE = PACKAGE + " FOR UPDATE OF package,ownership"

GRANT = """
SELECT grant_id,root_unit_id
FROM team_management_grants
WHERE grant_id=:grant_id AND manager_user_id=:actor_id AND action='task:assign'
  AND valid_from<=:at AND (valid_until IS NULL OR :at<valid_until)
  AND (revoked_at IS NULL OR :at<revoked_at)
  AND (
    root_unit_id=:unit_id OR (
      include_descendants AND EXISTS(
        SELECT 1 FROM organisation_unit_closure
        WHERE ancestor_unit_id=root_unit_id AND descendant_unit_id=:unit_id
      )
    )
  )
FOR UPDATE
"""

MEMBERSHIP = """
SELECT membership_id
FROM team_memberships
WHERE user_id=:user_id AND unit_id=:unit_id AND state='active'
  AND assignment_eligible AND valid_from<=:starts_at
  AND (valid_until IS NULL OR :ends_at<=valid_until)
FOR UPDATE
"""

UPDATE_PACKAGE = """
UPDATE canonical_work_packages
SET estimated_minutes=:estimated_minutes,remaining_minutes=:remaining_minutes,
    due_at=:due_at,priority=:priority,
    priority_override_reason=:priority_override_reason,
    state=CASE WHEN state='pending' THEN 'ready' ELSE state END,
    version=version+1,updated_at=:now
WHERE package_id=:package_id AND version=:expected_version
RETURNING version
"""

COMMANDS = """
SELECT * FROM work_package_commands
WHERE command_id=:command_id OR idempotency_key=:idempotency_key
ORDER BY command_id FOR UPDATE
"""

INSERT_COMMAND = """
INSERT INTO work_package_commands(
 command_id,idempotency_key,request_hash,package_id,actor_user_id,
 expected_version,result_version,operation,occurred_at)
VALUES (
 :command_id,:idempotency_key,:request_hash,:package_id,:actor_user_id,
 :expected_version,:result_version,'update',:occurred_at)
"""

INSERT_HISTORY = """
INSERT INTO work_package_history(
 history_id,package_id,version,actor_user_id,event_type,evidence,occurred_at)
VALUES (
 :history_id,:package_id,:version,:actor_user_id,'planned_and_reserved',
 CAST(:evidence AS jsonb),:occurred_at)
"""
