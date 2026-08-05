"""SQL writes for serialisable organisation merge commands."""

INSERT_COMMAND = """
INSERT INTO organisation_merge_commands(command_id,idempotency_key,request_hash,reason_hash,
 actor_user_id,source_unit_ids,source_expected_versions,source_result_versions,
 successor_unit_id,successor_expected_version,successor_result_version,authority_map,occurred_at)
VALUES (:command_id,:idempotency_key,:request_hash,:reason_hash,:actor_user_id,
 CAST(:source_ids AS uuid[]),CAST(:source_expected AS bigint[]),CAST(:source_results AS bigint[]),
 :successor_id,:successor_expected,:successor_result,CAST(:authority_map AS jsonb),:occurred_at)
RETURNING command_id
"""

INSERT_DISPOSITION = """
INSERT INTO organisation_merge_dispositions(command_id,record_kind,record_id,expected_version,
 action,target_unit_id,replacement_id)
VALUES (:command_id,:record_kind,:record_id,:expected_version,:action,
 :target_unit_id,:replacement_id)
RETURNING record_id
"""

ADVANCE_EPOCHS = """
WITH principals AS (
 SELECT user_id principal_id,unit_id scope_unit_id FROM team_memberships
 WHERE unit_id=ANY(CAST(:source_ids AS uuid[])) OR unit_id=:successor_id
 UNION SELECT manager_user_id,root_unit_id FROM team_management_grants
 WHERE root_unit_id=ANY(CAST(:source_ids AS uuid[])) OR root_unit_id=:successor_id
)
INSERT INTO effective_authority_epochs(principal_id,scope_unit_id,epoch,advanced_at)
SELECT principal_id,scope_unit_id,1,:occurred_at FROM principals
ON CONFLICT (principal_id,scope_unit_id) DO UPDATE SET
 epoch=effective_authority_epochs.epoch + 1,advanced_at=EXCLUDED.advanced_at
"""

INSERT_AUDIT = """
INSERT INTO coeus_audit_events(event_id,event_type,occurred_at,actor_user_id,metadata)
VALUES (:event_id,:event_type,:occurred_at,:actor_user_id,CAST(:payload AS jsonb))
ON CONFLICT (event_id) DO NOTHING
"""

INSERT_OUTBOX = """
INSERT INTO coeus_outbox(event_id,aggregate_id,aggregate_version,event_type,payload)
VALUES (:event_id,:aggregate_id,:aggregate_version,:event_type,CAST(:payload AS jsonb))
ON CONFLICT (aggregate_id,aggregate_version,event_type) DO NOTHING
"""
