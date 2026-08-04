"""SQL for scheduled and exact-boundary personnel transfers."""

LOAD_COMMAND = """
SELECT * FROM organisation_personnel_transfers
WHERE command_id=:command_id OR idempotency_key=:idempotency_key
ORDER BY command_id
"""

LOAD_DUE = """
SELECT * FROM organisation_personnel_transfers
WHERE status='pending' AND effective_at<=:effective_at
ORDER BY effective_at,command_id LIMIT :limit
"""

LOCK_TRANSFER = """
SELECT * FROM organisation_personnel_transfers
WHERE command_id=:command_id FOR UPDATE
"""

LOCK_MEMBERSHIPS = """
SELECT membership_id FROM team_memberships
WHERE user_id=:user_id OR membership_id IN (:source_membership_id,:target_membership_id)
ORDER BY membership_id FOR UPDATE
"""

INSPECT = """
SELECT source.version source_version,source.state source_state,
 source.assignment_eligible source_assignment_eligible,source.valid_from source_valid_from,
 source.valid_until source_valid_until,target.version target_version,
 target.is_active target_active,target.category target_category,
 (SELECT count(*) FROM team_task_ownership WHERE owning_unit_id=:source_unit_id
   AND state NOT IN ('completed','cancelled')) active_task_legs,
 COALESCE((SELECT string_agg(item.membership_id::text || ':' || item.version::text || ':' ||
   item.unit_id::text || ':' || item.state || ':' || item.valid_from::text || ':' ||
   COALESCE(item.valid_until::text,''),',' ORDER BY item.valid_from,item.membership_id)
   FROM team_memberships item WHERE item.user_id=:user_id),'') membership_state
FROM team_memberships source
JOIN organisation_units target ON target.unit_id=:target_unit_id
WHERE source.membership_id=:source_membership_id AND source.user_id=:user_id
 AND source.unit_id=:source_unit_id
"""

OVERLAP = """
SELECT membership_id FROM team_memberships
WHERE user_id=:user_id AND membership_id<>:source_membership_id AND state<>'cancelled'
 AND tstzrange(valid_from,valid_until,'[)') &&
     tstzrange(:effective_at,CAST(NULL AS timestamptz),'[)')
LIMIT 1
"""

INSERT_TRANSFER = """
INSERT INTO organisation_personnel_transfers(command_id,idempotency_key,request_hash,
 reason_hash,reason,actor_user_id,source_membership_id,target_membership_id,user_id,
 source_unit_id,target_unit_id,expected_membership_version,expected_target_unit_version,
 target_role,assignment_eligible,effective_at,source_authorising_grant_id,
 target_authorising_grant_id,status,source_result_version,target_result_version,
 failure_code,scheduled_at,applied_at)
VALUES (:command_id,:idempotency_key,:request_hash,:reason_hash,:reason,:actor_user_id,
 :source_membership_id,:target_membership_id,:user_id,:source_unit_id,:target_unit_id,
 :expected_membership_version,:expected_target_unit_version,:target_role,
 :assignment_eligible,:effective_at,:source_authorising_grant_id,
 :target_authorising_grant_id,'pending',:expected_membership_version,0,'',:occurred_at,NULL)
RETURNING command_id
"""

END_SOURCE = """
UPDATE team_memberships SET state='ended',assignment_eligible=false,
 valid_until=:effective_at,version=version + 1,updated_at=:occurred_at
WHERE membership_id=:source_membership_id AND user_id=:user_id
 AND unit_id=:source_unit_id AND version=:expected_membership_version
 AND state='active' AND valid_until IS NULL AND valid_from<:effective_at
RETURNING version
"""

INSERT_TARGET = """
INSERT INTO team_memberships(membership_id,user_id,unit_id,role,state,
 assignment_eligible,valid_from,valid_until,created_by_user_id,reason,provenance,version)
VALUES (:target_membership_id,:user_id,:target_unit_id,:target_role,'active',
 :assignment_eligible,:effective_at,NULL,:actor_user_id,:reason,'personnel-transfer',1)
RETURNING version
"""

MARK_APPLIED = """
UPDATE organisation_personnel_transfers SET status='applied',
 source_result_version=:source_result_version,target_result_version=:target_result_version,
 failure_code='',applied_at=:occurred_at WHERE command_id=:command_id AND status='pending'
RETURNING command_id
"""

MARK_BLOCKED = """
UPDATE organisation_personnel_transfers SET status='blocked',failure_code=:failure_code
WHERE command_id=:command_id AND status='pending' RETURNING command_id
"""
