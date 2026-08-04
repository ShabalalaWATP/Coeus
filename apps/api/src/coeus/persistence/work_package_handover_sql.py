"""SQL for atomic accountable-owner handover."""

PACKAGE = """
SELECT package.*,ownership.version ownership_version,
       ownership.state ownership_state,ownership.owning_unit_id ownership_unit_id
FROM canonical_work_packages package
JOIN team_task_ownership ownership
  ON ownership.ticket_id=package.ticket_id AND ownership.workflow_leg=package.workflow_leg
WHERE package.package_id=:package_id
"""
PACKAGE_FOR_UPDATE = PACKAGE + " FOR UPDATE OF package,ownership"

GRANT = """
SELECT grant_id,root_unit_id,version FROM team_management_grants
WHERE grant_id=:grant_id AND manager_user_id=:actor_id AND action='task:assign'
  AND valid_from<=:at AND (valid_until IS NULL OR :at<valid_until)
  AND (revoked_at IS NULL OR :at<revoked_at)
  AND (root_unit_id=:unit_id OR (include_descendants AND EXISTS(
    SELECT 1 FROM organisation_unit_closure
    WHERE ancestor_unit_id=root_unit_id AND descendant_unit_id=:unit_id)))
FOR UPDATE
"""

ACCOUNT = """
SELECT user_id,is_active,roles,credential_version,source_hash
FROM identity_account_projection WHERE user_id=:user_id FOR UPDATE
"""

TICKET_AUTHORITY = """
SELECT version,canonical_hash,payload
FROM coeus_ticket_aggregates WHERE ticket_id=:ticket_id
"""
TICKET_AUTHORITY_FOR_UPDATE = TICKET_AUTHORITY + " FOR UPDATE"

MEMBERSHIP = """
SELECT membership_id,unit_id,version FROM team_memberships
WHERE user_id=:user_id AND state='active' AND assignment_eligible
  AND valid_from<=:start AND (valid_until IS NULL OR :end<=valid_until)
FOR UPDATE
"""

PARTICIPANTS = """
SELECT user_id,role,active,created_at,ended_at FROM work_package_participants
WHERE package_id=:package_id ORDER BY user_id,role FOR UPDATE
"""

RESERVATIONS = """
SELECT reservation_id,user_id,starts_at,ends_at,reserved_minutes,state,version
FROM capacity_reservations WHERE package_id=:package_id AND state IN ('held','active')
ORDER BY reservation_id FOR UPDATE
"""

DEPENDENCIES = """
SELECT package_id,predecessor_package_id FROM work_package_dependencies
WHERE package_id=:package_id OR predecessor_package_id=:package_id
ORDER BY package_id,predecessor_package_id FOR UPDATE
"""

UPDATE_PACKAGE = """
UPDATE canonical_work_packages
SET accountable_user_id=:target_user_id,version=version+1,updated_at=:at
WHERE package_id=:package_id AND version=:expected_version
RETURNING version
"""

END_SOURCE = """
UPDATE work_package_participants SET active=false,ended_at=:at
WHERE package_id=:package_id AND user_id=:source_user_id AND role='accountable' AND active
"""

END_TARGET_CONTRIBUTOR = """
UPDATE work_package_participants SET active=false,ended_at=:at
WHERE package_id=:package_id AND user_id=:target_user_id AND role='contributor' AND active
"""

ADD_TARGET = """
INSERT INTO work_package_participants(package_id,user_id,role,active,created_at,ended_at)
VALUES (:package_id,:target_user_id,'accountable',true,:at,NULL)
ON CONFLICT (package_id,user_id,role)
DO UPDATE SET active=true,created_at=EXCLUDED.created_at,ended_at=NULL
"""

RELEASE_RESERVATION = """
UPDATE capacity_reservations SET state='released',version=version+1,updated_at=:at
WHERE reservation_id=:reservation_id AND version=:expected_version AND state IN ('held','active')
RETURNING version
"""

COMMANDS = """
SELECT * FROM work_package_handover_commands
WHERE command_id=:command_id OR (
 actor_user_id=:actor_user_id AND idempotency_key=:idempotency_key)
ORDER BY command_id FOR UPDATE
"""

INSERT_COMMAND = """
INSERT INTO work_package_handover_commands(
 command_id,idempotency_key,request_hash,preview_hash,package_id,source_user_id,target_user_id,
 actor_user_id,expected_package_version,result_package_version,released_reservation_count,
 replacement_reservation_count,occurred_at)
VALUES (:command_id,:idempotency_key,:request_hash,:preview_hash,:package_id,:source_user_id,
 :target_user_id,:actor_user_id,:expected_package_version,:result_package_version,
 :released_count,:replacement_count,:occurred_at)
"""

INSERT_HISTORY = """
INSERT INTO work_package_history(
 history_id,package_id,version,actor_user_id,event_type,evidence,occurred_at)
VALUES (:history_id,:package_id,:version,:actor_user_id,'accountable_handover',
 CAST(:evidence AS jsonb),:occurred_at)
"""
