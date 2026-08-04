"""SQL for transactional organisation membership lifecycle commands."""

LOAD_COMMAND = """
SELECT * FROM organisation_membership_commands
WHERE command_id=:command_id OR idempotency_key=:idempotency_key
ORDER BY command_id
"""

INSPECT = """
SELECT unit_row.version unit_version,
 COALESCE(membership.version,0) membership_version,
 (SELECT count(*) FROM team_task_ownership WHERE owning_unit_id=:unit_id
   AND state NOT IN ('completed','cancelled')) active_task_legs,
 unit_row.unit_id::text || ':' || unit_row.version::text || ':' ||
 COALESCE((SELECT string_agg(item.membership_id::text || ':' || item.version::text || ':' ||
   item.unit_id::text || ':' || item.state || ':' || item.valid_from::text || ':' ||
   COALESCE(item.valid_until::text,''),',' ORDER BY item.valid_from,item.membership_id)
   FROM team_memberships item WHERE item.user_id=:user_id),'') state_value
FROM organisation_units unit_row
LEFT JOIN team_memberships membership ON membership.membership_id=:membership_id
WHERE unit_row.unit_id=:unit_id
"""

LOCK_MEMBERSHIPS = """
SELECT membership_id FROM team_memberships
WHERE user_id=:user_id OR membership_id=:membership_id
ORDER BY membership_id FOR UPDATE
"""

OVERLAP = """
SELECT membership_id FROM team_memberships
WHERE user_id=:user_id AND membership_id<>:membership_id AND state<>'cancelled'
 AND tstzrange(valid_from,valid_until,'[)') &&
     tstzrange(:valid_from,CAST(NULL AS timestamptz),'[)')
LIMIT 1
"""

INSERT_MEMBERSHIP = """
INSERT INTO team_memberships(membership_id,user_id,unit_id,role,state,
 assignment_eligible,valid_from,valid_until,created_by_user_id,reason,provenance,version)
VALUES (:membership_id,:user_id,:unit_id,:role,'active',:assignment_eligible,
 :valid_from,NULL,:actor_user_id,:reason,'manual',1)
RETURNING version
"""

UPDATE_MEMBERSHIP = """
UPDATE team_memberships SET role=:role,assignment_eligible=:assignment_eligible,
 reason=:reason,version=version + 1,updated_at=:occurred_at
WHERE membership_id=:membership_id AND user_id=:user_id AND unit_id=:unit_id
 AND version=:expected_version AND state='active' AND valid_until IS NULL
 AND valid_from=:valid_from
RETURNING version
"""

END_MEMBERSHIP = """
UPDATE team_memberships SET state='ended',assignment_eligible=false,
 valid_until=:valid_until,reason=:reason,version=version + 1,updated_at=:occurred_at
WHERE membership_id=:membership_id AND user_id=:user_id AND unit_id=:unit_id
 AND version=:expected_version AND state='active' AND valid_until IS NULL
 AND valid_from=:valid_from AND valid_from<:valid_until
RETURNING version
"""

INSERT_COMMAND = """
INSERT INTO organisation_membership_commands(command_id,idempotency_key,request_hash,
 reason_hash,operation,actor_user_id,membership_id,user_id,unit_id,authorising_grant_id,
 expected_version,result_version,role,assignment_eligible,valid_from,valid_until,occurred_at)
VALUES (:command_id,:idempotency_key,:request_hash,:reason_hash,:operation,:actor_user_id,
 :membership_id,:user_id,:unit_id,:authorising_grant_id,:expected_version,:result_version,
 :role,:assignment_eligible,:valid_from,:valid_until,:occurred_at)
RETURNING command_id
"""
