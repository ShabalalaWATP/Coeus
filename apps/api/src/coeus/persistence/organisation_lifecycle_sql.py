"""SQL statements for previewed create/edit organisation commands."""

LOAD_COMMAND = """
SELECT * FROM organisation_unit_commands
WHERE command_id=:command_id OR idempotency_key=:idempotency_key
ORDER BY command_id
"""

INSERT_COMMAND = """
INSERT INTO organisation_unit_commands(command_id,idempotency_key,request_hash,operation,
 actor_user_id,unit_id,authorising_grant_id,expected_version,result_version,
 topology_revision_id,occurred_at)
VALUES (:command_id,:idempotency_key,:request_hash,:operation,:actor_user_id,:unit_id,
 :authorising_grant_id,:expected_version,:result_version,:topology_revision_id,:occurred_at)
RETURNING command_id
"""

INSERT_UNIT = """
INSERT INTO organisation_units(unit_id,name,short_name,category,parent_unit_id,is_active,
 valid_from,valid_until,time_zone,description,provenance,version)
VALUES (:unit_id,:name,:short_name,:category,:parent_unit_id,true,:occurred_at,NULL,
 :time_zone,:description,'manual',1) RETURNING unit_id
"""

INSERT_CLOSURE = """
INSERT INTO organisation_unit_closure(ancestor_unit_id,descendant_unit_id,depth)
SELECT ancestor_unit_id,:unit_id,depth + 1 FROM organisation_unit_closure
WHERE descendant_unit_id=:parent_unit_id
UNION ALL SELECT :unit_id,:unit_id,0
"""

INSERT_REVISION = """
INSERT INTO organisation_topology_revisions(revision_id,unit_id,parent_unit_id,path,
 valid_from,valid_until,change_command_id,changed_by_user_id)
SELECT :revision_id,:unit_id,:parent_unit_id,
 array_agg(ancestor_unit_id ORDER BY depth DESC),:occurred_at,NULL,:command_id,:actor_user_id
FROM organisation_unit_closure WHERE descendant_unit_id=:unit_id
RETURNING revision_id
"""

UPDATE_UNIT = """
UPDATE organisation_units SET name=:name,short_name=:short_name,time_zone=:time_zone,
 description=:description,version=version + 1,updated_at=now()
WHERE unit_id=:unit_id AND version=:expected_version AND is_active
RETURNING version
"""

INSERT_AUDIT = """
INSERT INTO coeus_audit_events(event_id,event_type,occurred_at,actor_user_id,metadata)
VALUES (:event_id,:event_type,:occurred_at,:actor_user_id,CAST(:payload AS jsonb))
ON CONFLICT (event_id) DO NOTHING
"""

INSERT_OUTBOX = """
INSERT INTO coeus_outbox(event_id,aggregate_id,aggregate_version,event_type,payload)
VALUES (:event_id,:unit_id,:result_version,:event_type,CAST(:payload AS jsonb))
ON CONFLICT (aggregate_id,aggregate_version,event_type) DO NOTHING
"""
