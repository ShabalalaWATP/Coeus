"""SQL writes for serialisable organisation split commands."""

INSERT_COMMAND = """
INSERT INTO organisation_split_commands(command_id,idempotency_key,request_hash,reason_hash,
 actor_user_id,source_unit_id,parent_unit_id,source_expected_version,parent_expected_version,
 source_result_version,parent_result_version,successor_specs,source_authorising_grant_id,
 parent_authorising_grant_id,occurred_at)
VALUES (:command_id,:idempotency_key,:request_hash,:reason_hash,:actor_user_id,:source_id,
 :parent_id,:source_expected,:parent_expected,:source_result,:parent_result,
 CAST(:successor_specs AS jsonb),:source_grant_id,:parent_grant_id,:occurred_at)
RETURNING command_id
"""

INSERT_DISPOSITION = """
INSERT INTO organisation_split_dispositions(command_id,record_kind,record_id,expected_version,
 action,target_unit_id,replacement_id)
VALUES (:command_id,:record_kind,:record_id,:expected_version,:action,
 :target_unit_id,:replacement_id) RETURNING record_id
"""

INSERT_SUCCESSOR = """
INSERT INTO organisation_units(unit_id,name,short_name,category,parent_unit_id,is_active,
 valid_from,valid_until,time_zone,description,provenance,version,created_at,updated_at)
VALUES (:unit_id,:name,:short_name,:category,:parent_id,true,:occurred_at,NULL,:time_zone,
 :description,'organisation_split',1,:occurred_at,:occurred_at) RETURNING version
"""

INSERT_SELF_CLOSURE = """
INSERT INTO organisation_unit_closure(ancestor_unit_id,descendant_unit_id,depth)
VALUES (:unit_id,:unit_id,0) RETURNING descendant_unit_id
"""

INSERT_PARENT_CLOSURE = """
INSERT INTO organisation_unit_closure(ancestor_unit_id,descendant_unit_id,depth)
SELECT ancestor_unit_id,:unit_id,depth + 1 FROM organisation_unit_closure
WHERE descendant_unit_id=:parent_id RETURNING ancestor_unit_id
"""

INSERT_SUCCESSOR_REVISION = """
INSERT INTO organisation_topology_revisions(revision_id,unit_id,parent_unit_id,path,valid_from,
 valid_until,change_command_id,changed_by_user_id)
SELECT :revision_id,:unit_id,:parent_id,
 array_agg(ancestor_unit_id ORDER BY depth DESC),:occurred_at,NULL,:command_id,:actor_user_id
FROM organisation_unit_closure WHERE descendant_unit_id=:unit_id RETURNING revision_id
"""

ADVANCE_EPOCHS = """
WITH principals AS (
 SELECT user_id principal_id,unit_id scope_unit_id FROM team_memberships
 WHERE unit_id=:source_id OR unit_id=ANY(CAST(:successor_ids AS uuid[]))
 UNION SELECT manager_user_id,root_unit_id FROM team_management_grants
 WHERE root_unit_id IN (:source_id,:parent_id)
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
