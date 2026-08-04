"""SQL for predecessor cancellation dispositions."""

PACKAGE = """
SELECT package.*,ownership.version ownership_version,ownership.state ownership_state
FROM canonical_work_packages package
JOIN team_task_ownership ownership ON ownership.ticket_id=package.ticket_id
 AND ownership.workflow_leg=package.workflow_leg
WHERE package.package_id=:package_id
"""
GRANT = """
SELECT grant_id,version FROM team_management_grants
WHERE grant_id=:grant_id AND manager_user_id=:actor_id AND action='task:assign'
 AND valid_from<=:at AND (valid_until IS NULL OR :at<valid_until)
 AND (revoked_at IS NULL OR :at<revoked_at) FOR UPDATE
"""
GRAPH = """
SELECT candidate.package_id,candidate.version,
 COALESCE(array_agg(edge.predecessor_package_id)
 FILTER (WHERE edge.predecessor_package_id IS NOT NULL),'{}') predecessors
FROM canonical_work_packages candidate
LEFT JOIN work_package_dependencies edge ON edge.package_id=candidate.package_id
WHERE candidate.ticket_id=:ticket_id AND candidate.workflow_leg=:leg
GROUP BY candidate.package_id ORDER BY candidate.package_id LIMIT 129
"""
CANCEL_PACKAGE = """
UPDATE canonical_work_packages SET state='cancelled',remaining_minutes=0,
 version=version+1,updated_at=:at
WHERE package_id=:package_id AND version=:version RETURNING version
"""
BUMP_PACKAGE = """
UPDATE canonical_work_packages SET version=version+1,updated_at=:at
WHERE package_id=:package_id AND version=:version RETURNING version
"""
DELETE_EDGE = """
DELETE FROM work_package_dependencies
WHERE package_id=:package_id AND predecessor_package_id=:predecessor_id
"""
INSERT_EDGE = """
INSERT INTO work_package_dependencies(
 package_id,predecessor_package_id,created_by_user_id,created_at)
VALUES (:package_id,:predecessor_id,:actor_id,:at)
"""
HISTORY = """
INSERT INTO work_package_history(
 history_id,package_id,version,actor_user_id,event_type,evidence,occurred_at)
VALUES (:history_id,:package_id,:version,:actor_id,:event,CAST(:evidence AS jsonb),:at)
"""
COMMAND = """
INSERT INTO predecessor_cancellation_commands(
 command_id,actor_user_id,idempotency_key,request_hash,package_id,
 expected_package_version,result_package_version,dispositions,occurred_at)
VALUES (:command_id,:actor_id,:key,:hash,:package_id,:expected_version,
 :result_version,CAST(:dispositions AS jsonb),:at)
"""
REPLAY = """
SELECT * FROM predecessor_cancellation_commands WHERE command_id=:command_id OR
 (actor_user_id=:actor_id AND idempotency_key=:key) ORDER BY command_id FOR UPDATE
"""
AUDIT = """
INSERT INTO coeus_audit_events(event_id,event_type,occurred_at,actor_user_id,metadata)
VALUES (:event_id,'work_package_predecessor_cancelled',:at,:actor_id,
 CAST(:evidence AS jsonb))
"""
OUTBOX = """
INSERT INTO coeus_outbox(event_id,aggregate_id,aggregate_version,event_type,payload)
VALUES (:event_id,:package_id,:version,'work_package_predecessor_cancelled',
 CAST(:evidence AS jsonb))
"""
