"""Mutation SQL for integrated workspace operations."""

UPSERT_POLICY = """
INSERT INTO team_workspace_policies(
 unit_id,service_target_hours,planning_cadence,planning_weekday,planning_local_time,
 planning_duration_minutes,version,updated_by_user_id,updated_at
) VALUES (
 :unit,:service,:cadence,:weekday,CAST(:local_time AS time),:duration,:version,:actor,:at
) ON CONFLICT(unit_id) DO UPDATE SET
 service_target_hours=EXCLUDED.service_target_hours,
 planning_cadence=EXCLUDED.planning_cadence,
 planning_weekday=EXCLUDED.planning_weekday,
 planning_local_time=EXCLUDED.planning_local_time,
 planning_duration_minutes=EXCLUDED.planning_duration_minutes,
 version=EXCLUDED.version,updated_by_user_id=EXCLUDED.updated_by_user_id,
 updated_at=EXCLUDED.updated_at
"""

INSERT_EXPORT = """
INSERT INTO workspace_export_jobs(
 export_id,actor_user_id,unit_id,include_descendants,authorising_grant_id,
 authorising_grant_version,command_id,idempotency_key,request_hash,state,row_count,
 snapshot_payload,handling_marking,created_at,expires_at
) VALUES (
 :export,:actor,:unit,:descendants,:grant,:grant_version,:command,:key,:hash,
 'ready',:rows,CAST(:snapshot AS jsonb),:handling,:at,:expires
)
"""

INSERT_COMMAND = """
INSERT INTO workspace_productivity_commands(
 command_id,actor_user_id,idempotency_key,request_hash,operation,result,occurred_at
) VALUES (:command,:actor,:key,:hash,:operation,CAST(:result AS jsonb),:at)
"""
